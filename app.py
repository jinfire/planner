import altair as alt
import pandas as pd
import streamlit as st

import main
from advisor import build_intro_message, build_rank_explanation, recommend_portfolios
from simulator.cpi import fetch_cpi
from simulator.data import fetch_extended_series, intersect_tickers
from simulator.strategy import ConstantWithdrawalStrategy

ACCENT = "#0E9F6E"
RANK_BADGES = {1: "🥇", 2: "🥈", 3: "🥉"}

st.set_page_config(page_title="은퇴 포트폴리오 Advisor", page_icon="📊", layout="wide")


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


def allocation_donut(weights: dict[str, float]) -> alt.Chart:
    df = pd.Series(weights, name="비중").reset_index()
    df.columns = ["티커", "비중"]
    df["구성"] = df["티커"] + " " + df["비중"].map(lambda w: f"{w:.0%}")
    return (
        alt.Chart(df)
        .mark_arc(innerRadius=70, outerRadius=130, stroke="white", strokeWidth=2)
        .encode(
            theta=alt.Theta("비중:Q", stack=True),
            order=alt.Order("비중:Q", sort="descending"),
            color=alt.Color(
                "구성:N",
                sort=alt.SortField("비중", order="descending"),
                scale=alt.Scale(scheme="set2"),
                legend=alt.Legend(title="자산 배분", orient="right"),
            ),
            tooltip=["티커:N", alt.Tooltip("비중:Q", format=".0%")],
        )
        .properties(height=300)
    )


def trajectory_area(trajectory_in_10m: pd.Series) -> alt.Chart:
    df = trajectory_in_10m.rename("자산가치").reset_index()
    df.columns = ["날짜", "자산가치"]
    # st.line_chart defaults to an interactive (zoomable) Altair chart - built
    # manually here without .interactive(), since there's nothing worth zooming
    # into on a simple trajectory line. Also sidesteps a Vega-Lite quirk where a
    # field name containing "." silently breaks the data binding.
    gradient = alt.Gradient(
        gradient="linear",
        stops=[alt.GradientStop(color="white", offset=0), alt.GradientStop(color=ACCENT, offset=1)],
        x1=1, x2=1, y1=1, y2=0,
    )
    return (
        alt.Chart(df)
        .mark_area(line={"color": ACCENT, "strokeWidth": 2}, color=gradient)
        .encode(x=alt.X("날짜:T", title=None), y=alt.Y("자산가치:Q", title="자산가치 (천만원)"))
        .properties(height=220)
    )


results = load_results()

st.title("📊 은퇴 포트폴리오 Advisor")
st.caption(f"사전계산된 {len(results):,}개 조합 중에서 조건에 맞는 3개를 추천합니다.")

with st.sidebar:
    st.header("조건 입력")
    total_assets = st.number_input(
        "총 자산 (원)", min_value=0, value=2_000_000_000, step=10_000_000, format="%d"
    )
    st.caption(f"= {total_assets:,}원")
    withdrawal_rate = st.selectbox(
        "인출률",
        main.WITHDRAWAL_RATE_OPTIONS,
        index=main.WITHDRAWAL_RATE_OPTIONS.index(0.04),
        format_func=lambda r: f"{r:.1%}",
    )
    st.caption(f"= 월 {total_assets * withdrawal_rate / 12:,.0f}원")
    st.subheader("Score 가중치 (뭘 중요하게 볼지)")
    st.caption(
        "셋 다 같은 1~10 척도의 독립적인 다이얼입니다 - 서로 더해서 어떤 "
        "합계가 돼야 하는 건 아니고, 각자 그 항목을 얼마나 중요하게 볼지만 정해요."
    )
    # 1~10 scale is just main.SCORE_*_WEIGHT / 10 - retirement_score() is a weighted
    # sum, so scaling every weight by the same constant changes none of the actual
    # rankings, only how the dial reads to a user (main.py's batch-time defaults stay
    # on their own 0~100 scale, unrelated to this UI's scale choice).
    survival_weight = st.slider(
        "자산 유지",
        1.0,
        10.0,
        main.SCORE_SURVIVAL_WEIGHT / 10,
        step=1.0,
        help="과거 데이터 기준, 이 배분으로 인출을 시작했을 때 돈이 바닥나지 "
        "않고 끝까지 유지된 비율. 높일수록 '안 망하는 것'을 최우선으로 봄. "
        "필터가 아니라 가중치라, 100%가 아닌 조합도 다른 항목이 훨씬 좋으면 뽑힐 수 있음.",
    )
    growth_weight = st.slider(
        "성장 (CAGR)",
        1.0,
        10.0,
        main.SCORE_GROWTH_WEIGHT / 10,
        step=1.0,
        help="연평균 수익률. 높일수록 자산이 더 많이 불어나는 배분을 선호함.",
    )
    risk_weight = st.slider(
        "변동성 (MDD)",
        1.0,
        10.0,
        main.SCORE_RISK_WEIGHT / 10,
        step=1.0,
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
        st.write(build_intro_message(survival_weight, growth_weight, risk_weight))

        universe, full_cpi = load_universe()
        for i, rec in enumerate(recs, 1):
            with st.container(border=True):
                st.subheader(f"{RANK_BADGES.get(i, '')} {i}순위")
                st.write(build_rank_explanation(rec, i, total_assets))

                chart_col, metric_col = st.columns([3, 2])
                with chart_col:
                    st.altair_chart(allocation_donut(rec["weights"]), width="stretch")
                with metric_col:
                    # Deliberately worded differently from the "자산 유지"/"성장"/
                    # "변동성" score-weight dials in the sidebar - those are input
                    # preferences, these are the actual measured numbers for this
                    # recommendation, and reusing the same words made the two easy
                    # to mix up.
                    st.metric("자산 고갈률", f"{1 - rec['survival_probability']:.1%}")
                    st.metric("연 수익률", f"{rec['cagr']:.2%}")
                    st.metric("최대낙폭", f"{rec['mdd']:.2%}")
                    st.metric("월 인출액", f"{rec['monthly_withdrawal']:,.0f}원")
                    st.metric("최종 자산", f"{total_assets * rec['final_value']:,.0f}원")

                strategy = ConstantWithdrawalStrategy(rec["weights"], withdrawal_rate, main.REBALANCE_FREQ)
                close, dividends = intersect_tickers(universe, strategy.tickers)
                trajectory = strategy.simulate(close, dividends, full_cpi).value
                # result.value is normalized to initial_capital=1.0 - scale by this
                # user's actual total_assets and show in 천만원 units so the y-axis
                # reads as real money instead of an abstract multiplier.
                trajectory_in_10m = trajectory * total_assets / 10_000_000
                st.caption("자산 가치 추이 (단위: 천만원)")
                st.altair_chart(trajectory_area(trajectory_in_10m), width="stretch")
