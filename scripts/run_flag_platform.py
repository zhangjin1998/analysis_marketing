#!/usr/bin/env python3
import argparse
import os
import sys
from datetime import datetime

import pandas as pd

# 将项目根目录加入 sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.patterns_flag import scan_flag_platform_all  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="扫描 翻倍后旗型/平台 并导出CSV")
    parser.add_argument("--limit", type=int, default=0, help="限制股票数（0为不限制）")
    parser.add_argument("--exclude-st", action="store_true", help="剔除ST")
    parser.add_argument("--require-breakout", action="store_true", help="需要突破确认（放量+上破上沿）")
    parser.add_argument("--topk", type=int, default=0, help="仅导出前K条（按score排序），0为全部")
    parser.add_argument("--out", type=str, default="", help="导出CSV路径（默认data/patterns/自动命名）")

    args = parser.parse_args()

    df = scan_flag_platform_all(limit=args.limit, exclude_st=args.exclude_st, require_breakout=args.require_breakout)
    if df is None or df.empty:
        print("未命中任何标的")
        return

    # 打分与排序：ret_up高、width小、drawdown适中（越小越好）、std/vol收缩越小越好、r2高
    def _safe(v, default):
        try:
            if pd.isna(v):
                return default
            return float(v)
        except Exception:
            return default

    def score_row(r):
        ret_up = _safe(r.get("ret_up"), 0.0)
        width = _safe(r.get("width"), 1.0)
        drawdown = _safe(r.get("drawdown"), 1.0)
        r2 = _safe(r.get("r2"), 0.0)
        vol_shrink_flag = _safe(r.get("vol_shrink_flag"), 1.0)
        std_shrink_flag = _safe(r.get("std_shrink_flag"), 1.0)
        std_shrink_base = _safe(r.get("std_shrink_base"), 1.0)
        # 简单线性组合
        score = (
            2.0 * ret_up
            - 1.0 * width
            - 0.5 * drawdown
            + 0.5 * r2
            - 0.3 * vol_shrink_flag
            - 0.3 * min(std_shrink_flag, std_shrink_base)
        )
        return score

    df = df.copy()
    df["score"] = df.apply(score_row, axis=1)
    df = df.sort_values(["score", "ret_up"], ascending=[False, False])

    if args.topk and args.topk > 0:
        df_out = df.head(args.topk).reset_index(drop=True)
    else:
        df_out = df.reset_index(drop=True)

    # 导出
    if not args.out:
        os.makedirs("data/patterns", exist_ok=True)
        tag = "noST" if args.exclude_st else "all"
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"data/patterns/flag_platform_{tag}_{now}.csv"
    else:
        fname = args.out
        os.makedirs(os.path.dirname(fname), exist_ok=True)
    df_out.to_csv(fname, index=False, encoding="utf-8-sig")

    # 预览前20条
    print(f"已导出: {fname}. 共有 {len(df_out)} 条命中。预览：")
    cols_show = [c for c in ["code", "type", "ret_up", "width", "drawdown", "r2", "ma20_slope_pct", "score"] if c in df_out.columns]
    print(df_out[cols_show].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
