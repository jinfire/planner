import pandas as pd
import streamlit as st

import main
from advisor import explain_recommendation, recommend_portfolios
from simulator.cpi import fetch_cpi
from simulator.data import fetch_extended_series, intersect_tickers
from simulator.strategy import ConstantWithdrawalStrategy

st.set_page_config(page_title="은퇴 포트폴리오 Advisor", layout="centered")


@st.cache_data
def load_results() -> pd.DataFrame:
    return pd.read_csv(main.RESULTS_CSV)


@st.cache_resource
def load_universe():
    # Only needed to redraw a chosen recommendation's asset trajectory - the
    # recommendation itself comes straight from the precomputed results.csv, no
    # simulation required. Cached so this (slow, network-bound) fetch happens once
    # per server process, not once per button click.
    universe = fetch_extended_series(main.TICKERS, main.START, main.END)
    full_cpi = fetch_cpi(main.START, main.END)
    return universe, full_cpi


results = load_results()

st.title("은퇴 포트폴리오 Advisor")
st.caption(f"사전계산된 {len(results):,}개 조합 중에서 조건에 맞는 3개를 추천합니다.")

with st.sidebar:
    st.header("조건 입력")
    total_assets = st.number_input(
        "총 자산 (원)", min_value=0, value=500_000_000, step=10_000_000, format="%d"
    )
    st.caption(f"= {total_assets:,}원")
    withdrawal_rate = st.selectbox(
        "인출률",
        main.WITHDRAWAL_RATE_OPTIONS,
        index=main.WITHDRAWAL_RATE_OPTIONS.index(0.04),
        format_func=lambda r: f"{r:.1%}",
    )
    st.subheader("Score 가중치 (뭘 중요하게 볼지)")
    st.caption(
        "셋 다 같은 0~100 척도의 독립적인 다이얼입니다 - 서로 더해서 어떤 "
        "합계가 돼야 하는 건 아니고, 각자 그 항목을 얼마나 중요하게 볼지만 정해요."
    )
    survival_weight = st.slider(
        "생존확률",
        0.0,
        100.0,
        main.SCORE_SURVIVAL_WEIGHT,
        step=5.0,
        help="과거 데이터 기준, 이 배분으로 인출을 시작했을 때 돈이 바닥나지 "
        "않고 끝까지 버틴 비율. 높일수록 '안 망하는 것'을 최우선으로 봄.",
    )
    growth_weight = st.slider(
        "성장 (CAGR)",
        0.0,
        100.0,
        main.SCORE_GROWTH_WEIGHT,
        step=5.0,
        help="연평균 수익률. 높일수록 자산이 더 많이 불어나는 배분을 선호함.",
    )
    risk_weight = st.slider(
        "낙폭 방어 (MDD)",
        0.0,
        100.0,
        main.SCORE_RISK_WEIGHT,
        step=5.0,
        help="최대낙폭. 최고점 대비 가장 많이 떨어졌을 때 몇 %나 떨어졌는지. "
        "높일수록 급락이 덜한(변동성 낮은) 배분을 선호함.",
    )
    # longevity(고갈 지연)는 "이미 둘 다 고갈된 배분끼리"만 비교하는 미세
    # 타이브레이커라 사용자가 조절할 만큼 체감 차이가 없어서 고정값으로 뺌 -
    # main.SCORE_LONGEVITY_WEIGHT 참고
    longevity_weight = main.SCORE_LONGEVITY_WEIGHT
    submitted = st.button("추천 받기", type="primary")

if submitted:
    recs = recommend_portfolios(
        results,
        main.TICKERS,
        withdrawal_rate,
        total_assets,
        survival_weight=survival_weight,
        growth_weight=growth_weight,
        risk_weight=risk_weight,
        longevity_weight=longevity_weight,
        top_n=3,
    )

    if not recs:
        st.warning("이 인출률에 해당하는 사전계산 결과가 없습니다.")
    else:
        universe, full_cpi = load_universe()
        for i, rec in enumerate(recs, 1):
            st.subheader(f"{i}순위")
            col1, col2 = st.columns(2)
            with col1:
                st.bar_chart(pd.Series(rec["weights"], name="비중"))
            with col2:
                st.metric("생존확률", f"{rec['survival_probability']:.1%}")
                st.metric("월 인출액", f"{rec['monthly_withdrawal']:,.0f}원")
                st.metric("CAGR / MDD", f"{rec['cagr']:.2%} / {rec['mdd']:.2%}")

            st.text(explain_recommendation(rec, i))

            strategy = ConstantWithdrawalStrategy(rec["weights"], withdrawal_rate, main.REBALANCE_FREQ)
            close, dividends = intersect_tickers(universe, strategy.tickers)
            trajectory = strategy.simulate(close, dividends, full_cpi).value
            # Vega-Lite (the chart engine behind st.line_chart) treats "." in a field
            # name as nested-field access, so a name like "... = 1.0" silently breaks
            # the data binding and renders empty axes with no line - name it without
            # a period instead.
            st.caption("자산 가치 (초기 자본 = 1배 기준)")
            st.line_chart(trajectory.rename("자산가치"))
            st.divider()
