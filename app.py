import math

import folium
import requests
import streamlit as st
from streamlit_folium import st_folium


# =========================================================
# 1. 웹페이지 기본 설정
# =========================================================

st.set_page_config(
    page_title="화순-광주 병목구간 시뮬레이터",
    page_icon="🚦",
    layout="wide",
)

COLORS = {
    "background": "#12161b",
    "panel": "#1a2129",
    "panel_2": "#212a33",
    "line": "#2b3540",
    "text": "#e9edf1",
    "dim": "#8b98a5",
    "route": "#3f8c9b",
    "green": "#3ea88f",
    "amber": "#dba13c",
    "red": "#d1495b",
}

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: {COLORS["background"]};
        color: {COLORS["text"]};
    }}

    [data-testid="stMetric"] {{
        background-color: {COLORS["panel_2"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 12px;
        padding: 14px;
    }}

    [data-testid="stMetricLabel"],
    [data-testid="stMetricValue"] {{
        color: {COLORS["text"]};
    }}

    .stCaption,
    [data-testid="stCaptionContainer"] {{
        color: {COLORS["dim"]};
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# 2. 운송·이송 유형별 경로 설정
# =========================================================
#
# main:
#   우리가 지정한 병목구간을 반드시 지나는 주 경로
#
# alt:
#   주 경로의 V/C가 1.10 이상일 때만 활성화되는 비상 우회 경로
#
# 프로그램은 두 경로의 이동시간을 비교하여 경로를 선택하지 않습니다.
#

SCENARIOS = {
    "뇌졸중 환자 이송": {
        "start": {
            "name": "화순전남대학교병원",
            "address": "전라남도 화순군 화순읍 서양로 322",
            "coord": (35.0593108, 127.0026119),
        },
        "end": {
            "name": "전남대학교병원",
            "address": "광주광역시 동구 제봉로 42",
            "coord": (35.1417259, 126.9220237),
        },
        "main": {
            "name": "너릿재 경유",
            "waypoint": (35.0780200, 126.9568000),
            "capacity": 2200,
            "bottleneck_km": 3.0,
            "bottleneck_share": 0.45,
        },
        "alt": {
            "name": "칠구재 경유",
            "waypoint": (35.0899158, 126.9137359),
            "capacity": 1800,
            "bottleneck_share": 0.55,
        },
    },

    "식품 이동": {
        "start": {
            "name": "화순농협 하나로마트 본점",
            "address": "전라남도 화순군 화순읍 쌍충로 74",
            "coord": (35.0733000, 126.9875000),
        },
        "end": {
            "name": "효천1도시개발구역",
            "address": "광주광역시 남구 임암동 대표 지점",
            "coord": (35.1020585, 126.8739019),
        },
        "main": {
            "name": "칠구재 경유",
            "waypoint": (35.0899158, 126.9137359),
            "capacity": 1800,
            "bottleneck_km": 3.5,
            "bottleneck_share": 0.55,
        },
        "alt": {
            "name": "너릿재 경유",
            "waypoint": (35.0780200, 126.9568000),
            "capacity": 2200,
            "bottleneck_share": 0.45,
        },
    },

    "혈액제제 운송": {
        "start": {
            "name": "대한적십자사 광주전남혈액원",
            "address": "광주광역시 남구 서문대로 406",
            "coord": (35.1040940, 126.8805230),
        },
        "end": {
            "name": "화순전남대학교병원",
            "address": "전라남도 화순군 화순읍 서양로 322",
            "coord": (35.0593108, 127.0026119),
        },
        "main": {
            "name": "칠구재 경유",
            "waypoint": (35.0899158, 126.9137359),
            "capacity": 1800,
            "bottleneck_km": 3.5,
            "bottleneck_share": 0.55,
        },
        "alt": {
            "name": "너릿재 경유",
            "waypoint": (35.0780200, 126.9568000),
            "capacity": 2200,
            "bottleneck_share": 0.45,
        },
    },

    "화학약품 운송": {
        "start": {
            "name": "광주과학기술원(GIST)",
            "address": "광주광역시 북구 첨단과기로 123",
            "coord": (35.2277554, 126.8413052),
        },
        "end": {
            "name": "한국화학융합시험연구원 동물대체시험센터",
            "address": "전라남도 화순군 화순읍 산단길 12-67",
            "coord": (35.0322932, 126.9598542),
        },
        "main": {
            "name": "너릿재 경유",
            "waypoint": (35.0780200, 126.9568000),
            "capacity": 2200,
            "bottleneck_km": 3.0,
            "bottleneck_share": 0.45,
        },
        "alt": {
            "name": "칠구재 경유",
            "waypoint": (35.0899158, 126.9137359),
            "capacity": 1800,
            "bottleneck_share": 0.55,
        },
    },
}


# =========================================================
# 3. 날씨에 따른 시뮬레이션 설정
# =========================================================

WEATHER_CAPACITY_FACTOR = {
    "맑음": 1.00,
    "눈/비": 0.80,
}

WEATHER_TIME_FACTOR = {
    "맑음": 1.00,
    "눈/비": 1.15,
}


# =========================================================
# 4. 지도 경로 불러오기
# =========================================================

def haversine_km(point_a, point_b):
    """두 위도·경도 지점 사이의 직선거리를 km로 계산합니다."""

    lat1, lon1 = map(math.radians, point_a)
    lat2, lon2 = map(math.radians, point_b)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    value = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    return 6371.0 * 2 * math.asin(math.sqrt(value))


def make_fallback_route(start, waypoint, end):
    """
    외부 경로 서버 연결 실패 시 사용하는 예비 경로입니다.
    시작점-경유점-도착점을 근사선으로 연결합니다.
    """

    points = [start, waypoint, end]
    coords = []
    total_distance = 0.0

    for first, second in zip(points[:-1], points[1:]):
        total_distance += haversine_km(first, second)

        for index in range(35):
            ratio = index / 34

            coords.append(
                (
                    first[0] + (second[0] - first[0]) * ratio,
                    first[1] + (second[1] - first[1]) * ratio,
                )
            )

    total_distance *= 1.25
    duration_min = total_distance / 42.0 * 60.0

    return {
        "coords": coords,
        "distance_km": total_distance,
        "duration_min": duration_min,
        "source": "fallback",
    }


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_route(start, waypoint, end):
    """OSRM에서 실제 자동차 도로 경로를 불러옵니다."""

    coordinate_text = ";".join(
        f"{longitude},{latitude}"
        for latitude, longitude in (start, waypoint, end)
    )

    url = (
        "https://router.project-osrm.org/"
        f"route/v1/driving/{coordinate_text}"
    )

    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }

    headers = {
        "User-Agent": "hwasun-gwangju-school-simulator/1.0"
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()

        data = response.json()

        if data.get("code") != "Ok":
            raise RuntimeError("OSRM 경로 요청에 실패했습니다.")

        routes = data.get("routes", [])

        if not routes:
            raise RuntimeError("경로 데이터가 비어 있습니다.")

        route = routes[0]

        coords = [
            (latitude, longitude)
            for longitude, latitude
            in route["geometry"]["coordinates"]
        ]

        return {
            "coords": coords,
            "distance_km": route["distance"] / 1000,
            "duration_min": route["duration"] / 60,
            "source": "osrm",
        }

    except Exception:
        return make_fallback_route(
            start,
            waypoint,
            end,
        )


# =========================================================
# 5. 교통량에 따른 병목 상태 계산
# =========================================================

def bpr_multiplier(volume, capacity):
    """BPR 함수로 교통량 증가에 따른 시간 증가율을 계산합니다."""

    if capacity <= 0:
        return math.inf

    return 1 + 0.15 * (volume / capacity) ** 4


def classify_bottleneck(vc_ratio):
    """
    V/C 단계:
    0.70 미만       원활
    0.70~0.90 미만  혼잡
    0.90~1.10 미만  심각한 혼잡
    1.10 이상       통행 한계 초과 및 자동 우회
    """

    if vc_ratio < 0.70:
        return {
            "status": "원활",
            "color": COLORS["green"],
            "rerouted": False,
        }

    if vc_ratio < 0.90:
        return {
            "status": "혼잡",
            "color": COLORS["amber"],
            "rerouted": False,
        }

    if vc_ratio < 1.10:
        return {
            "status": "심각한 혼잡",
            "color": COLORS["red"],
            "rerouted": False,
        }

    return {
        "status": "통행 한계 초과 · 자동 우회",
        "color": COLORS["red"],
        "rerouted": True,
    }


def calculate_route_time(
    base_minutes,
    volume,
    route_data,
    weather,
):
    """경로 중 병목구간에만 BPR 혼잡 효과를 적용합니다."""

    effective_capacity = (
        route_data["capacity"]
        * WEATHER_CAPACITY_FACTOR[weather]
    )

    vc_ratio = volume / effective_capacity

    congestion_multiplier = bpr_multiplier(
        volume,
        effective_capacity,
    )

    bottleneck_share = route_data["bottleneck_share"]

    traffic_adjusted_time = base_minutes * (
        1
        + bottleneck_share
        * (congestion_multiplier - 1)
    )

    final_time = (
        traffic_adjusted_time
        * WEATHER_TIME_FACTOR[weather]
    )

    return {
        "time": final_time,
        "vc": vc_ratio,
        "effective_capacity": effective_capacity,
    }


def calculate_simulation(scenario, volume, weather):
    """
    주 경로와 우회 경로의 시간을 비교하지 않습니다.
    주 경로 V/C가 1.10 이상일 때만 우회 경로를 사용합니다.
    """

    start = scenario["start"]["coord"]
    end = scenario["end"]["coord"]

    main_route = fetch_route(
        start,
        scenario["main"]["waypoint"],
        end,
    )

    alt_route = fetch_route(
        start,
        scenario["alt"]["waypoint"],
        end,
    )

    main_result = calculate_route_time(
        main_route["duration_min"],
        volume,
        scenario["main"],
        weather,
    )

    bottleneck = classify_bottleneck(
        main_result["vc"]
    )

    alt_result = calculate_route_time(
        alt_route["duration_min"],
        volume,
        scenario["alt"],
        weather,
    )

    rerouted = bottleneck["rerouted"]

    active_time = (
        alt_result["time"]
        if rerouted
        else main_result["time"]
    )

    return {
        "main_route": main_route,
        "alt_route": alt_route,
        "main_result": main_result,
        "alt_result": alt_result,
        "bottleneck": bottleneck,
        "rerouted": rerouted,
        "active_time": active_time,
    }


# =========================================================
# 6. 주 경로에서 병목구간만 추출
# =========================================================

def nearest_route_index(coords, point):
    return min(
        range(len(coords)),
        key=lambda index: haversine_km(
            coords[index],
            point,
        ),
    )


def extract_bottleneck_segment(
    coords,
    waypoint,
    length_km,
):
    """주 경로 중 병목 지점 주변의 지정 길이만 추출합니다."""

    if len(coords) < 2:
        return coords

    center_index = nearest_route_index(
        coords,
        waypoint,
    )

    half_length = length_km / 2

    left_index = center_index
    left_distance = 0.0

    while (
        left_index > 0
        and left_distance < half_length
    ):
        left_distance += haversine_km(
            coords[left_index],
            coords[left_index - 1],
        )
        left_index -= 1

    right_index = center_index
    right_distance = 0.0

    while (
        right_index < len(coords) - 1
        and right_distance < half_length
    ):
        right_distance += haversine_km(
            coords[right_index],
            coords[right_index + 1],
        )
        right_index += 1

    segment = coords[
        left_index:right_index + 1
    ]

    if len(segment) < 2:
        segment = coords[
            max(0, center_index - 1):
            min(len(coords), center_index + 2)
        ]

    return segment


# =========================================================
# 7. 지도 생성
# =========================================================

def add_legend(map_object):
    legend_html = (
        '<div style="position:fixed;bottom:28px;left:28px;z-index:9999;'
        'background:white;color:#222;padding:10px 12px;border:1px solid #bbb;'
        'border-radius:7px;font-size:12px;line-height:1.7;'
        'box-shadow:0 1px 5px rgba(0,0,0,.25);">'
        '<b>지도 표시</b><br>'
        f'<span style="color:{COLORS["route"]};font-weight:700;">━━</span> 주 경로<br>'
        f'<span style="color:{COLORS["dim"]};font-weight:700;">┄┄</span> 비활성 우회 경로<br>'
        f'<span style="color:{COLORS["green"]};font-weight:700;">━━</span> 병목 원활 / 활성 우회<br>'
        f'<span style="color:{COLORS["amber"]};font-weight:700;">━━</span> 병목 혼잡<br>'
        f'<span style="color:{COLORS["red"]};font-weight:700;">━━</span> 병목 심각·통행 한계 초과'
        '</div>'
    )

    map_object.get_root().html.add_child(
        folium.Element(legend_html)
    )


def make_map(scenario, result):
    start = scenario["start"]["coord"]
    end = scenario["end"]["coord"]

    center = [
        (start[0] + end[0]) / 2,
        (start[1] + end[1]) / 2,
    ]

    map_object = folium.Map(
        location=center,
        zoom_start=11,
        tiles="CartoDB positron",
        control_scale=True,
    )

    folium.Marker(
        start,
        tooltip=f"출발: {scenario['start']['name']}",
        popup=(
            f"<b>{scenario['start']['name']}</b>"
            f"<br>{scenario['start']['address']}"
        ),
        icon=folium.Icon(
            color="green",
            icon="play",
        ),
    ).add_to(map_object)

    folium.Marker(
        end,
        tooltip=f"도착: {scenario['end']['name']}",
        popup=(
            f"<b>{scenario['end']['name']}</b>"
            f"<br>{scenario['end']['address']}"
        ),
        icon=folium.Icon(
            color="red",
            icon="stop",
        ),
    ).add_to(map_object)

    # 주 경로
    folium.PolyLine(
        result["main_route"]["coords"],
        color=(
            COLORS["dim"]
            if result["rerouted"]
            else COLORS["route"]
        ),
        weight=4 if result["rerouted"] else 6,
        opacity=0.45 if result["rerouted"] else 0.88,
        dash_array="7, 7" if result["rerouted"] else None,
        tooltip=(
            f"주 경로: {scenario['main']['name']} · "
            f"{result['main_route']['distance_km']:.1f}km"
        ),
    ).add_to(map_object)

    # 우회 경로
    folium.PolyLine(
        result["alt_route"]["coords"],
        color=(
            COLORS["green"]
            if result["rerouted"]
            else COLORS["dim"]
        ),
        weight=8 if result["rerouted"] else 4,
        opacity=0.95 if result["rerouted"] else 0.65,
        dash_array=None if result["rerouted"] else "8, 8",
        tooltip=(
            (
                "활성 우회 경로"
                if result["rerouted"]
                else "대기 중인 우회 경로"
            )
            + f": {scenario['alt']['name']}"
        ),
    ).add_to(map_object)

    bottleneck_segment = extract_bottleneck_segment(
        result["main_route"]["coords"],
        scenario["main"]["waypoint"],
        scenario["main"]["bottleneck_km"],
    )

    # 병목구간만 초록→주황→빨강으로 변화
    folium.PolyLine(
        bottleneck_segment,
        color=result["bottleneck"]["color"],
        weight=11,
        opacity=0.98,
        tooltip=(
            f"병목구간 · {result['bottleneck']['status']} · "
            f"V/C {result['main_result']['vc']:.2f}"
        ),
    ).add_to(map_object)

    folium.CircleMarker(
        scenario["main"]["waypoint"],
        radius=7,
        color=result["bottleneck"]["color"],
        fill=True,
        fill_color=result["bottleneck"]["color"],
        fill_opacity=0.95,
        tooltip=(
            f"병목 지점 · "
            f"{result['bottleneck']['status']}"
        ),
    ).add_to(map_object)

    if result["rerouted"]:
        folium.Marker(
            scenario["main"]["waypoint"],
            tooltip="주 경로 통행 한계 초과",
            icon=folium.DivIcon(
                html=(
                    f'<div style="color:{COLORS["red"]};font-size:30px;'
                    'font-weight:900;transform:translate(-7px,-21px);'
                    'text-shadow:0 0 3px white;">×</div>'
                )
            ),
        ).add_to(map_object)

    folium.CircleMarker(
        scenario["alt"]["waypoint"],
        radius=5,
        color=(
            COLORS["green"]
            if result["rerouted"]
            else COLORS["dim"]
        ),
        fill=True,
        fill_color=(
            COLORS["green"]
            if result["rerouted"]
            else COLORS["dim"]
        ),
        fill_opacity=0.80,
        tooltip=(
            f"우회 경유 지점 · "
            f"{scenario['alt']['name']}"
        ),
    ).add_to(map_object)

    all_points = (
        result["main_route"]["coords"]
        + result["alt_route"]["coords"]
        + [start, end]
    )

    map_object.fit_bounds(all_points)
    add_legend(map_object)

    return map_object


# =========================================================
# 8. 웹사이트 화면
# =========================================================

st.caption(
    "HWASUN ↔ GWANGJU · BOTTLENECK SIMULATOR"
)

st.title(
    "화순-광주 물류·이송 병목구간 시뮬레이터"
)

st.write(
    "지정한 병목구간을 지나는 경로를 항상 주 경로로 사용하며, "
    "교통량이 통행 한계를 넘을 때만 자동으로 우회합니다."
)

scenario_name = st.selectbox(
    "운송·이송 유형",
    options=list(SCENARIOS.keys()),
)

scenario = SCENARIOS[scenario_name]

# HTML을 사용하지 않고 Streamlit 기본 구성요소로 표시하여
# 코드블록처럼 보이던 오류를 방지합니다.
with st.container(border=True):
    st.markdown(
        f"**출발:** {scenario['start']['name']}"
    )
    st.caption(
        scenario["start"]["address"]
    )

    st.markdown(
        f"**도착:** {scenario['end']['name']}"
    )
    st.caption(
        scenario["end"]["address"]
    )

    st.divider()

    st.markdown(
        f"**고정 주 경로:** {scenario['main']['name']}"
    )
    st.markdown(
        f"**비상 우회 경로:** {scenario['alt']['name']}"
    )

left_column, right_column = st.columns(
    [3, 2]
)

with left_column:
    volume = st.slider(
        "시간당 교통량",
        min_value=200,
        max_value=4000,
        value=800,
        step=100,
    )

with right_column:
    weather = st.radio(
        "기상 조건",
        options=["맑음", "눈/비"],
        horizontal=True,
    )

effective_capacity = (
    scenario["main"]["capacity"]
    * WEATHER_CAPACITY_FACTOR[weather]
)

reroute_threshold = (
    effective_capacity * 1.10
)

st.caption(
    f"현재 교통량 {volume:,}대/시간 · "
    f"날씨 반영 병목 용량 {effective_capacity:,.0f}대/시간 · "
    f"자동 우회 기준 {reroute_threshold:,.0f}대/시간 이상"
)

with st.spinner(
    "경로와 병목 상태를 계산하는 중입니다..."
):
    simulation = calculate_simulation(
        scenario,
        volume,
        weather,
    )

    route_map = make_map(
        scenario,
        simulation,
    )

st_folium(
    route_map,
    height=620,
    use_container_width=True,
    returned_objects=[],
)

status_column, route_column, time_column = st.columns(
    3
)

with status_column:
    st.metric(
        "병목구간 상태",
        simulation["bottleneck"]["status"],
    )

with route_column:
    if simulation["rerouted"]:
        route_label = "자동 우회 경로"
        route_value = scenario["alt"]["name"]
    else:
        route_label = "현재 주 경로"
        route_value = scenario["main"]["name"]

    st.metric(
        route_label,
        route_value,
    )

with time_column:
    st.metric(
        "예상 이동시간",
        f"{simulation['active_time']:.1f}분",
    )

with st.container(border=True):
    if simulation["rerouted"]:
        st.error(
            "주 경로의 통행 한계를 초과하여 "
            "비상 우회 경로가 활성화되었습니다."
        )
    else:
        st.success(
            "지정한 병목구간을 지나는 "
            "주 경로를 계속 사용합니다."
        )

    st.write(
        f"V/C {simulation['main_result']['vc']:.2f} · "
        f"유효 용량 "
        f"{simulation['main_result']['effective_capacity']:,.0f}대/시간 · "
        f"기상 조건 {weather}"
    )

if (
    simulation["main_route"]["source"] != "osrm"
    or simulation["alt_route"]["source"] != "osrm"
):
    st.warning(
        "외부 경로 서버 연결이 원활하지 않아 "
        "일부 경로가 근사선으로 표시되었습니다. "
        "잠시 후 새로고침해 주세요."
    )

st.divider()

st.caption(
    "병목구간의 도로 용량, 눈·비에 따른 용량 감소율, "
    "V/C 단계 기준은 실제 자료 확보 전 사용하는 시뮬레이션 가정값입니다. "
    "본 프로그램은 주 경로와 우회 경로의 시간을 비교하여 "
    "경로를 선택하지 않습니다."
)
