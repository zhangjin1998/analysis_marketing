#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按形态筛选股票（基于 analyse_marketing 缓存/候选池）
示例：
  python3 scripts/run_patterns.py --all --patterns "强势后平台" --limit 0
  python3 scripts/run_patterns.py --candidates --patterns "三连阳,放量突破" --limit 500
输出：data/patterns/pattern_picks.csv
"""
import os
import argparse
import pandas as pd
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.patterns import (
    detect_patterns_on_all,
    detect_patterns_on_candidates,
    format_pattern_result,
)

def main():
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--all', action='store_true', help='在全缓存上筛选')
    g.add_argument('--candidates', action='store_true', help='仅在候选池上筛选')
    parser.add_argument('--patterns', type=str, required=True, help='形态名，逗号或空格分隔')
    parser.add_argument('--limit', type=int, default=0, help='限制股票数量（0表示不限）')
    parser.add_argument('--topk', type=int, default=100, help='输出前N条用于打印预览')
    stg = parser.add_mutually_exclusive_group()
    stg.add_argument('--exclude-st', action='store_true', help='剔除ST（默认）')
    stg.add_argument('--include-st', action='store_true', help='保留ST')
    args = parser.parse_args()

    # 解析形态列表
    raw = args.patterns.replace('，', ',').replace(' ', ',')
    names = [s.strip() for s in raw.split(',') if s.strip()]

    print("=" * 80)
    print("📊 形态选股 - 开始")
    print("形态:", names)
    print("范围:", "全缓存" if args.all else "候选池")
    print("限制:", args.limit)
    print("=" * 80)

    exclude_st = not args.include_st

    if args.all:
        picks_df, table = detect_patterns_on_all(names, limit=args.limit, exclude_st=exclude_st)
    else:
        picks_df, table = detect_patterns_on_candidates(names, limit=args.limit if args.limit > 0 else 200, exclude_st=exclude_st)

    # 输出与保存
    os.makedirs('data/patterns', exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    tag_st = 'noST' if exclude_st else 'withST'
    out_csv = f'data/patterns/pattern_picks_{tag_st}_{ts}.csv'

    if table is None or table.empty:
        print("⚠️ 未命中形态")
        # 也保存空文件，便于记录
        pd.DataFrame([], columns=['code','patterns']).to_csv(out_csv, index=False, encoding='utf-8-sig')
        print("已保存:", out_csv)
        return

    table.to_csv(out_csv, index=False, encoding='utf-8-sig')

    # 打印预览
    print()
    print(format_pattern_result(picks_df, table, top_k=args.topk))
    print()
    print("已保存:", out_csv)

if __name__ == '__main__':
    main()
