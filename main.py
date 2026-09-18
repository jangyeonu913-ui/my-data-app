from datetime import datetime, timedelta
import zoneinfo
import pandas as pd
import requests
import streamlit as st

# 페이지 기본 설정 (타이틀 및 레이아웃)
st.set_page_config(page_title="어제 박스오피스", layout="wide")


# 1시간 동안 API 호출 결과를 기억(캐싱)하는 함수
@st.cache_data(ttl=3600)
def fetch_box_office_data(api_key, target_date):
    """KOBIS API를 호출하여 dailyBoxOfficeList를 가져오는 함수"""
    url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {"key": api_key, "targetDt": target_date}

    # API 요청 보내기
    response = requests.get(url, params=params, timeout=10)

    # HTTP 상태 코드가 200(성공)이 아닌 경우 Exception 발생
    if response.status_code != 200:
        raise RuntimeError("API 서버 요청에 실패했습니다.")

    data = response.json()

    # KOBIS API 특성: 인증키 오류 시 status_code 200과 함께 'faultInfo' 응답 전달
    if "faultInfo" in data:
        message = data["faultInfo"].get("message", "알 수 없는 오류")
        raise ValueError(f"API 오류 발생: {message}")

    # 박스오피스 결과 및 영화 목록 파싱
    box_office_result = data.get("boxOfficeResult", {})
    movie_list = box_office_result.get("dailyBoxOfficeList", [])

    if not movie_list:
        raise ValueError("해당 날짜의 영화 목록 데이터가 비어 있습니다.")

    return movie_list


# 앱 화면 메인 타이틀
st.title("🎬 어제 일별 박스오피스")

# Secrets에서 KOBIS API 키 불러오기
try:
    API_KEY = st.secrets["KOBIS_KEY"]
except Exception:
    st.error("🔑 Secrets 설정을 확인해 주세요.")
    st.info(
        """
    **확인할 사항:**
    1. `.streamlit/secrets.toml` 또는 Streamlit Cloud Secrets에 `KOBIS_KEY`가 등록되어 있는지 확인해 주세요.
    2. 키 이름이 `KOBIS_KEY`와 정확히 일치하는지 확인해 주세요.
    """
    )
    st.stop()

# 한국 표준시(KST) 기준으로 '어제' 날짜 계산 (서버 시계 영향 방지)
kst = zoneinfo.ZoneInfo("Asia/Seoul")
yesterday = datetime.now(kst) - timedelta(days=1)
target_dt = yesterday.strftime("%Y%m%d")
display_date = yesterday.strftime("%Y년 %m월 %d일")

st.caption(f"📅 조회 기준일 (한국 시간 기준 어제): **{display_date}**")

# API 데이터 불러오기 시도
try:
    raw_movie_list = fetch_box_office_data(API_KEY, target_dt)

    # 파이썬 데이터프레임(DataFrame)으로 변환
    df = pd.DataFrame(raw_movie_list)

    # 문자열로 들어오는 숫자 데이터를 숫자형(int)으로 변환
    numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 순위 기준으로 정렬
    df = df.sort_values(by="rank", ascending=True)

    # 1. 1위 영화 지표 카드 (Metric) 표시
    top_movie = df.iloc[0]
    st.subheader(f"🥇 1위: {top_movie['movieNm']}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="당일 관객수", value=f"{top_movie['audiCnt']:,} 명"
        )
    with col2:
        st.metric(
            label="누적 관객수", value=f"{top_movie['audiAcc']:,} 명"
        )
    with col3:
        st.metric(
            label="스크린 수", value=f"{top_movie['scrnCnt']:,} 개"
        )

    st.divider()

    # 2. 관객수 상위 5편 막대그래프 표시
    st.subheader("📊 관객수 상위 5개 영화")
    top5_df = df.head(5)[["movieNm", "audiCnt"]].copy()

    # Streamlit 기본 막대그래프 (x: 영화명, y: 관객수)
    st.bar_chart(data=top5_df, x="movieNm", y="audiCnt", color="#FF4B4B")

    st.divider()

    # 3. 전체 박스오피스 표 표시
    st.subheader("📋 전체 순위 목록")

    # 표에 사용할 컬럼 선택 및 이름 변경
    table_df = df[
        ["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]
    ].copy()
    table_df.columns = [
        "순위",
        "영화명",
        "개봉일",
        "관객수",
        "누적관객",
        "스크린수",
    ]

    # 숫자 세 자릿수 콤마(,) 포맷팅 및 표 출력
    st.dataframe(
        table_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "관객수": st.column_config.NumberColumn(format="%d명"),
            "누적관객": st.column_config.NumberColumn(format="%d명"),
            "스크린수": st.column_config.NumberColumn(format="%d개"),
        },
    )

except ValueError as ve:
    st.warning("⚠️ 데이터를 불러오는 중 문제가 발생했습니다.")
    st.info(
        f"""
    **확인할 사항:**
    - {ve}
    - KOBIS_KEY가 올바른 인증키인지 확인해 주세요.
    - 영화진흥위원회 API 서비스 상태를 확인해 주세요.
    """
    )

except requests.exceptions.RequestException:
    st.error("🌐 네트워크 통신 오류가 발생했습니다.")
    st.info(
        """
    **확인할 사항:**
    - 인터넷 연결 상태를 확인해 주세요.
    - KOBIS API 서버가 정상 작동 중인지 확인해 주세요.
    """
    )

except Exception as e:
    st.error("❌ 알 수 없는 오류가 발생했습니다.")
    st.caption(f"오류 상세: {e}")
