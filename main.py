import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from pathlib import Path
import unicodedata
import io

# =========================
# 기본 설정
# =========================
st.set_page_config(
    page_title="극지식물 최적 EC 농도 연구",
    layout="wide"
)

# =========================
# 한글 폰트 CSS (깨짐 방지)
# =========================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR&display=swap');
html, body, [class*="css"] {
    font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
}
</style>
""", unsafe_allow_html=True)

PLOTLY_FONT = dict(family="Malgun Gothic, Apple SD Gothic Neo, sans-serif")

# =========================
# 유틸: 한글 파일 안전 탐색
# =========================
def normalize_name(name):
    return unicodedata.normalize("NFC", name)

def find_file_by_normalized_name(directory: Path, target_name: str):
    target_n = normalize_name(target_name)
    for p in directory.iterdir():
        if normalize_name(p.name) == target_n:
            return p
    return None

# =========================
# 데이터 로딩
# =========================
DATA_DIR = Path("data")

@st.cache_data
def load_environment_data():
    with st.spinner("환경 데이터 로딩 중..."):
        result = {}
        for csv_name in [
            "송도고_환경데이터.csv",
            "하늘고_환경데이터.csv",
            "아라고_환경데이터.csv",
            "동산고_환경데이터.csv"
        ]:
            file_path = find_file_by_normalized_name(DATA_DIR, csv_name)
            if file_path is None:
                st.error(f"파일을 찾을 수 없습니다: {csv_name}")
                return None
            df = pd.read_csv(file_path)
            df["school"] = csv_name.split("_")[0]
            result[df["school"].iloc[0]] = df
        return result

@st.cache_data
def load_growth_data():
    with st.spinner("생육 결과 데이터 로딩 중..."):
        xlsx_path = None
        for p in DATA_DIR.iterdir():
            if p.suffix == ".xlsx":
                xlsx_path = p
                break

        if xlsx_path is None:
            st.error("생육 결과 XLSX 파일을 찾을 수 없습니다.")
            return None

        xls = pd.ExcelFile(xlsx_path)
        data = {}
        for sheet in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet)
            df["학교"] = sheet
            data[sheet] = df
        return data, xlsx_path.name

env_data = load_environment_data()
growth_data_tuple = load_growth_data()

if env_data is None or growth_data_tuple is None:
    st.stop()

growth_data, growth_filename = growth_data_tuple

# =========================
# 사이드바
# =========================
schools = ["전체"] + list(env_data.keys())
selected_school = st.sidebar.selectbox("학교 선택", schools)

# =========================
# 제목
# =========================
st.title("🌱 극지식물 최적 EC 농도 연구")

tab1, tab2, tab3 = st.tabs(["📖 실험 개요", "🌡️ 환경 데이터", "📊 생육 결과"])

# =========================
# Tab 1 : 실험 개요
# =========================
with tab1:
    st.subheader("연구 배경 및 목적")
    st.markdown("""
    극지식물은 제한된 환경 조건에서 생존하기 때문에  
    **EC(전기전도도)** 는 생육에 결정적인 요인이다.  
    본 연구는 학교별 서로 다른 EC 조건에서의 생육 결과를 비교하여  
    **최적 EC 농도**를 도출하는 것을 목적으로 한다.
    """)

    ec_table = pd.DataFrame({
        "학교명": ["송도고", "하늘고", "아라고", "동산고"],
        "EC 목표": [4.0, 2.0, 8.0, 6.0],
        "개체수": [29, 45, 106, 58],
        "색상": ["Blue", "Green", "Red", "Purple"]
    })
    st.table(ec_table)

    total_plants = sum(ec_table["개체수"])
    avg_temp = pd.concat(env_data.values())["temperature"].mean()
    avg_hum = pd.concat(env_data.values())["humidity"].mean()

    growth_all = pd.concat(growth_data.values())
    ec_map = {"송도고": 4.0, "하늘고": 2.0, "아라고": 8.0, "동산고": 6.0}
    growth_all["EC"] = growth_all["학교"].map(ec_map)
    optimal_ec = (
        growth_all.groupby("EC")["생중량(g)"]
        .mean()
        .idxmax()
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 개체수", f"{total_plants} 개")
    c2.metric("평균 온도", f"{avg_temp:.1f} ℃")
    c3.metric("평균 습도", f"{avg_hum:.1f} %")
    c4.metric("최적 EC", f"{optimal_ec}")

# =========================
# Tab 2 : 환경 데이터
# =========================
with tab2:
    st.subheader("학교별 환경 평균 비교")

    env_all = pd.concat(env_data.values())

    avg_env = env_all.groupby("school").mean(numeric_only=True).reset_index()

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=["평균 온도", "평균 습도", "평균 pH", "목표 EC vs 실측 EC"]
    )

    fig.add_bar(x=avg_env["school"], y=avg_env["temperature"], row=1, col=1)
    fig.add_bar(x=avg_env["school"], y=avg_env["humidity"], row=1, col=2)
    fig.add_bar(x=avg_env["school"], y=avg_env["ph"], row=2, col=1)

    target_ec = avg_env["school"].map(ec_map)
    fig.add_bar(x=avg_env["school"], y=target_ec, name="목표 EC", row=2, col=2)
    fig.add_bar(x=avg_env["school"], y=avg_env["ec"], name="실측 EC", row=2, col=2)

    fig.update_layout(font=PLOTLY_FONT, height=700)
    st.plotly_chart(fig, use_container_width=True)

    if selected_school != "전체":
        df = env_data[selected_school]
        st.subheader(f"{selected_school} 시계열 데이터")

        fig_ts = go.Figure()
        fig_ts.add_scatter(x=df["time"], y=df["temperature"], name="온도")
        fig_ts.add_scatter(x=df["time"], y=df["humidity"], name="습도")
        fig_ts.add_scatter(x=df["time"], y=df["ec"], name="EC")
        fig_ts.add_hline(y=ec_map[selected_school], line_dash="dash")

        fig_ts.update_layout(font=PLOTLY_FONT)
        st.plotly_chart(fig_ts, use_container_width=True)

    with st.expander("환경 데이터 원본 보기 / 다운로드"):
        st.dataframe(env_all)
        buffer = io.BytesIO()
        env_all.to_csv(buffer, index=False)
        buffer.seek(0)
        st.download_button(
            "CSV 다운로드",
            data=buffer,
            file_name="환경데이터_전체.csv",
            mime="text/csv"
        )

# =========================
# Tab 3 : 생육 결과
# =========================
with tab3:
    st.subheader("🥇 EC별 평균 생중량")

    ec_avg = growth_all.groupby("EC")["생중량(g)"].mean().reset_index()

    fig_ec = px.bar(
        ec_avg,
        x="EC",
        y="생중량(g)",
        text="생중량(g)"
    )
    fig_ec.update_layout(font=PLOTLY_FONT)
    st.plotly_chart(fig_ec, use_container_width=True)

    st.subheader("EC별 생육 지표 비교")

    fig2 = make_subplots(
        rows=2, cols=2,
        subplot_titles=["생중량", "잎 수", "지상부 길이", "개체수"]
    )

    fig2.add_bar(x=ec_avg["EC"], y=ec_avg["생중량(g)"], row=1, col=1)
    fig2.add_bar(
        x=growth_all.groupby("EC")["잎 수(장)"].mean().index,
        y=growth_all.groupby("EC")["잎 수(장)"].mean(),
        row=1, col=2
    )
    fig2.add_bar(
        x=growth_all.groupby("EC")["지상부 길이(mm)"].mean().index,
        y=growth_all.groupby("EC")["지상부 길이(mm)"].mean(),
        row=2, col=1
    )
    fig2.add_bar(
        x=growth_all.groupby("EC").size().index,
        y=growth_all.groupby("EC").size(),
        row=2, col=2
    )

    fig2.update_layout(font=PLOTLY_FONT, height=700)
    st.plotly_chart(fig2, use_container_width=True)

    st.subheader("학교별 생중량 분포")
    fig_box = px.box(
        growth_all,
        x="학교",
        y="생중량(g)",
        color="학교"
    )
    fig_box.update_layout(font=PLOTLY_FONT)
    st.plotly_chart(fig_box, use_container_width=True)

    st.subheader("상관관계 분석")
    c1, c2 = st.columns(2)
    with c1:
        fig_sc1 = px.scatter(
            growth_all,
            x="잎 수(장)",
            y="생중량(g)",
            trendline="ols"
        )
        fig_sc1.update_layout(font=PLOTLY_FONT)
        st.plotly_chart(fig_sc1, use_container_width=True)

    with c2:
        fig_sc2 = px.scatter(
            growth_all,
            x="지상부 길이(mm)",
            y="생중량(g)",
            trendline="ols"
        )
        fig_sc2.update_layout(font=PLOTLY_FONT)
        st.plotly_chart(fig_sc2, use_container_width=True)

    with st.expander("생육 데이터 원본 / XLSX 다운로드"):
        st.dataframe(growth_all)
        buffer = io.BytesIO()
        growth_all.to_excel(buffer, index=False, engine="openpyxl")
        buffer.seek(0)
        st.download_button(
            "XLSX 다운로드",
            data=buffer,
            file_name="생육결과_전체.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
