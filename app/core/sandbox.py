import httpx
from langchain.agents import AgentType, initialize_agent
from langchain.tools import tool
from langchain_ollama import ChatOllama
from RestrictedPython import compile_restricted, safe_globals

from app.config import settings

OUTPUT_MAX_CHARS = 4000


@tool
def open_meteo_analysis(
    location: str,
    start_date: str,
    end_date: str,
    variable: str = "temperature_2m",
) -> str:
    """
    Fetches weather time series from Open-Meteo for a location/date range.
    variable options: temperature_2m | precipitation | windspeed_10m
    """
    var_map = {
        "temperature_2m": "temperature_2m_max",
        "precipitation": "precipitation_sum",
        "windspeed_10m": "windspeed_10m_max",
    }
    daily_var = var_map.get(variable, "temperature_2m_max")

    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1&language=en&format=json"
    with httpx.Client(timeout=10) as client:
        geo_res = client.get(geo_url).json()

    if not geo_res.get("results"):
        return f"Could not find location: {location}"

    lat = geo_res["results"][0]["latitude"]
    lon = geo_res["results"][0]["longitude"]

    weather_url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily={daily_var}"
    )
    with httpx.Client(timeout=15) as client:
        data = client.get(weather_url).json()

    if "daily" not in data:
        return f"Error fetching weather data: {data}"

    values = data["daily"][daily_var]
    analysis_script = """
def analyze(values):
    if not values:
        return {"error": "No data"}
    valid = [v for v in values if v is not None]
    if not valid:
        return {"error": "No valid data"}
    n = len(valid)
    avg = sum(valid) / n
    variance = sum((x - avg) ** 2 for x in valid) / n
    std = variance ** 0.5 if variance > 0 else 0
    rolling_7 = [sum(valid[i-6:i+1])/7 for i in range(6, n)] if n > 6 else []
    anomalies = sum(1 for i, v in enumerate(valid) if std > 0 and abs((v - avg) / std) > 2)
    missing_pct = round((len(values) - len(valid)) / len(values) * 100, 1) if values else 0
    return {"average": round(avg, 2), "std_dev": round(std, 2),
            "rolling_7_avg": round(sum(rolling_7)/len(rolling_7), 2) if rolling_7 else None,
            "anomaly_count": anomalies, "missing_pct": missing_pct}
result = analyze(values)
"""
    loc = {}
    exec(compile_restricted(analysis_script, "<string>", "exec"), safe_globals, loc)
    ar = loc["analyze"](values)
    return (
        f"Location: {location} | {start_date} to {end_date} | {variable}\n"
        f"Avg: {ar.get('average')} | Std: {ar.get('std_dev')} | "
        f"7d rolling: {ar.get('rolling_7_avg')} | Anomalies: {ar.get('anomaly_count')} | Missing: {ar.get('missing_pct')}%"
    )[:OUTPUT_MAX_CHARS]


def get_agent_executor():
    if settings.sanity_mock:
        class MockAgent:
            def invoke(self, inputs):
                return {"output": "Mocked analysis: avg temp 20C."}
        return MockAgent()

    llm = ChatOllama(
        model=settings.ollama_chat_model,
        base_url=settings.ollama_base_url,
        temperature=0.0,
        timeout=60,
    )
    return initialize_agent(
        tools=[open_meteo_analysis],
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
        max_iterations=5,
        handle_parsing_errors=True,
        early_stopping_method="generate",
    )
