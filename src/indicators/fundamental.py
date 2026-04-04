"""
펀더멘털 지표 스코어링 모듈
PER, PBR, ROE, 매출성장률, 영업이익률, EPS성장률, 부채비율
"""

import numpy as np


def compute_all(info: dict, config: dict) -> dict:
    """펀더멘털 데이터로부터 종합 점수 계산"""
    details = {}
    signals = []

    # --- PER ---
    per = info.get("per")
    cfg_per = config["per"]
    if per and per > 0:
        if per < 10:
            per_score = 85
            signals.append(f"저PER ({per:.1f})")
        elif per < 20:
            per_score = 65
        elif per < 30:
            per_score = 45
        elif per < 50:
            per_score = 30
        else:
            per_score = 15
    else:
        per_score = 30  # 적자 또는 데이터 없음
    details["per"] = {"value": round(per, 2) if per else None, "score": per_score}

    # --- PBR ---
    pbr = info.get("pbr")
    cfg_pbr = config["pbr"]
    if pbr and pbr > 0:
        if pbr < 1:
            pbr_score = 80
            signals.append(f"저PBR ({pbr:.2f})")
        elif pbr < 2:
            pbr_score = 60
        elif pbr < 5:
            pbr_score = 40
        else:
            pbr_score = 20
    else:
        pbr_score = 40
    details["pbr"] = {"value": round(pbr, 2) if pbr else None, "score": pbr_score}

    # --- ROE ---
    roe = info.get("roe")
    cfg_roe = config["roe"]
    if roe is not None:
        roe_pct = roe * 100 if abs(roe) < 1 else roe  # 소수 vs 퍼센트 보정
        if roe_pct >= 20:
            roe_score = 90
            signals.append(f"고ROE ({roe_pct:.1f}%)")
        elif roe_pct >= cfg_roe["min"]:
            roe_score = 55 + (roe_pct - cfg_roe["min"]) * 2.5
        elif roe_pct > 0:
            roe_score = 35
        else:
            roe_score = 10
    else:
        roe_score = 40
    roe_score = np.clip(roe_score, 0, 100)
    details["roe"] = {"value": round(roe_pct, 2) if roe is not None else None, "score": round(roe_score, 1)}

    # --- 매출 성장률 ---
    rev_growth = info.get("revenue_growth")
    cfg_rev = config["revenue_growth"]
    if rev_growth is not None:
        rev_pct = rev_growth * 100 if abs(rev_growth) < 10 else rev_growth
        if rev_pct >= 30:
            rev_score = 90
            signals.append(f"고성장 매출 (YoY {rev_pct:.1f}%)")
        elif rev_pct >= cfg_rev["min_yoy"]:
            rev_score = 55 + (rev_pct - cfg_rev["min_yoy"]) * 1.5
        elif rev_pct > 0:
            rev_score = 40
        else:
            rev_score = 15
            signals.append(f"매출 역성장 (YoY {rev_pct:.1f}%)")
    else:
        rev_score = 40
    rev_score = np.clip(rev_score, 0, 100)
    details["revenue_growth"] = {"value": round(rev_pct, 2) if rev_growth is not None else None, "score": round(rev_score, 1)}

    # --- 영업이익률 ---
    op_margin = info.get("operating_margin")
    cfg_op = config["operating_margin"]
    if op_margin is not None:
        op_pct = op_margin * 100 if abs(op_margin) < 1 else op_margin
        if op_pct >= 20:
            op_score = 85
        elif op_pct >= cfg_op["min"]:
            op_score = 50 + (op_pct - cfg_op["min"]) * 2
        elif op_pct > 0:
            op_score = 35
        else:
            op_score = 10
    else:
        op_score = 40
    op_score = np.clip(op_score, 0, 100)
    details["operating_margin"] = {"value": round(op_pct, 2) if op_margin is not None else None, "score": round(op_score, 1)}

    # --- EPS 성장률 ---
    eps_growth = info.get("earnings_growth")
    cfg_eps = config["eps_growth"]
    if eps_growth is not None:
        eps_pct = eps_growth * 100 if abs(eps_growth) < 10 else eps_growth
        if eps_pct >= 30:
            eps_score = 85
        elif eps_pct >= cfg_eps["min_yoy"]:
            eps_score = 55 + (eps_pct - cfg_eps["min_yoy"]) * 1.5
        elif eps_pct > 0:
            eps_score = 40
        else:
            eps_score = 15
    else:
        eps_score = 40
    eps_score = np.clip(eps_score, 0, 100)
    details["eps_growth"] = {"value": round(eps_pct, 2) if eps_growth is not None else None, "score": round(eps_score, 1)}

    # --- 부채비율 ---
    debt = info.get("debt_to_equity") or info.get("debt_ratio")
    cfg_debt = config["debt_ratio"]
    if debt is not None:
        debt_val = debt if debt > 1 else debt * 100  # 비율 보정
        if debt_val <= 50:
            debt_score = 85
        elif debt_val <= 100:
            debt_score = 65
        elif debt_val <= cfg_debt["max"]:
            debt_score = 45
        else:
            debt_score = 15
            signals.append(f"고부채 ({debt_val:.0f}%)")
    else:
        debt_score = 50
    details["debt_ratio"] = {"value": round(debt_val, 1) if debt is not None else None, "score": round(debt_score, 1)}

    # --- 가중 합산 ---
    weights = {
        "per": cfg_per["weight"],
        "pbr": cfg_pbr["weight"],
        "roe": cfg_roe["weight"],
        "revenue_growth": cfg_rev["weight"],
        "operating_margin": cfg_op["weight"],
        "eps_growth": cfg_eps["weight"],
        "debt_ratio": cfg_debt["weight"],
    }
    total = sum(details[k]["score"] * weights[k] for k in weights)

    return {
        "score": round(total, 1),
        "details": details,
        "signals": signals,
    }
