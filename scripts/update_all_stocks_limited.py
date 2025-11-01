#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整更新所有股票数据 - 带限速控制
遵守 Tushare API 限制: 每分钟最多 50 次调用
"""
import os
import sys
import time
import pandas as pd
from datetime import datetime, timedelta
from tqdm import tqdm

# 设置 Tushare Token
os.environ['TUSHARE_TOKEN'] = 'b09f3c651f9fa367d9861d845052e8b4bb461543980a2daad4fff9c7'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'analyse_marketing'))

try:
    from analyse_marketing.utils import get_pro, cache_path, save_parquet, load_parquet, fetch_daily_history
except:
    import tushare as ts
    
def limit_sleep(call_count, start_time, min_interval=1.2):
    """
    限速控制：每分钟最多 50 次调用
    - 每次调用间隔最少 1.2 秒（这样每分钟最多 50 次）
    """
    elapsed = time.time() - start_time
    sleep_needed = call_count * min_interval - elapsed
    if sleep_needed > 0:
        time.sleep(sleep_needed)
    
    # 每分钟重置计数
    if elapsed >= 60:
        return 0, time.time()
    return call_count, start_time

def get_pro_simple():
    """获取 Tushare API"""
    import tushare as ts
    token = os.environ.get('TUSHARE_TOKEN')
    if not token:
        raise RuntimeError("❌ 未设置 TUSHARE_TOKEN")
    return ts.pro_api(token)

def fetch_all_stocks_latest():
    """获取所有股票的最新数据"""
    print("=" * 80)
    print("📊 完整更新所有股票数据（带限速）")
    print("=" * 80)
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 限速: 每分钟最多 50 次 API 调用")
    print()
    
    pro = get_pro_simple()
    cache_dir = "analyse_marketing/cache"
    
    # 获取所有缓存的股票列表
    daily_dir = os.path.join(cache_dir, 'daily')
    os.makedirs(daily_dir, exist_ok=True)
    
    all_files = [f for f in os.listdir(daily_dir) if f.endswith('.parquet')]
    print(f"📁 找到 {len(all_files)} 只缓存股票")
    
    # 统计需要更新的
    needs_update = []
    for file in all_files:
        code = file.replace('.parquet', '')
        cpath = os.path.join(daily_dir, file)
        try:
            df = pd.read_parquet(cpath)
            last_date = df.index[-1] if len(df) > 0 else 0
        except:
            last_date = 0
        needs_update.append((code, last_date))
    
    print(f"🔄 需要检查更新: {len(needs_update)} 只股票\n")
    
    # 更新逻辑
    updated_count = 0
    failed_count = 0
    call_count = 0
    minute_start = time.time()
    
    pbar = tqdm(total=len(needs_update), desc="进度")
    
    for code, last_date in needs_update:
        try:
            # 限速控制
            call_count += 1
            if call_count > 50:
                print(f"\n⏳ 达到分钟限制，等待中...")
                time.sleep(62)  # 等待超过 1 分钟
                call_count = 0
                minute_start = time.time()
            else:
                # 正常间隔
                elapsed = time.time() - minute_start
                expected_time = call_count * 1.2
                if expected_time > elapsed:
                    time.sleep(expected_time - elapsed)
            
            # 尝试增量拉取
            cpath = os.path.join(daily_dir, f"{code}.parquet")
            
            if os.path.exists(cpath):
                df = pd.read_parquet(cpath)
                if len(df) > 0:
                    last_trade_date = df.index[-1]
                    # 从最后日期的下一天开始拉取
                    start_date_str = str(int(last_trade_date) + 1)
                else:
                    start_date_str = "20230101"
            else:
                start_date_str = "20230101"
            
            # 调用 API
            df_new = pro.daily(ts_code=code, start_date=start_date_str, fields='ts_code,trade_date,open,high,low,close,vol,amount')
            
            if df_new is not None and len(df_new) > 0:
                if os.path.exists(cpath):
                    df_old = pd.read_parquet(cpath)
                    df_combined = pd.concat([df_old, df_new], ignore_index=True).drop_duplicates(subset=['trade_date'])
                    df_combined = df_combined.sort_values('trade_date')
                else:
                    df_combined = df_new.sort_values('trade_date')
                
                df_combined['trade_date'] = pd.to_datetime(df_combined['trade_date'])
                df_combined = df_combined.set_index('trade_date')
                save_parquet(df_combined, cpath)
                updated_count += 1
        
        except Exception as e:
            failed_count += 1
            pass
        
        pbar.update(1)
    
    pbar.close()
    
    print("\n" + "=" * 80)
    print(f"✅ 更新完成!")
    print(f"  成功更新: {updated_count} 只")
    print(f"  失败: {failed_count} 只")
    print(f"⏰ 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

if __name__ == "__main__":
    try:
        fetch_all_stocks_latest()
        
        # 更新完成后重新计算市场宽度
        print("\n📈 现在重新计算市场宽度...")
        os.system("python3 scripts/update_breadth_today.py")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        sys.exit(1)

