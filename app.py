import streamlit as st
import pandas as pd
import requests
from io import StringIO
import json
import os
from datetime import datetime

st.set_page_config(page_title="USSSA Fantasy Slow-Pitch", page_icon="🥎", layout="wide")

# USSSA green theme
st.markdown("""
    <style>
    .stApp { background-color: #f0f8f0; }
    </style>
""", unsafe_allow_html=True)

DEFAULT_URL = "https://web.usssa.com/sports/ConferenceUSSSA.asp?WTD=5&SA=1&State=0&ClassID=701&RR=400&MinAB=1&SeasonID=29&StatisticType=2&Sort1=OBA&sort2=&sort3="

# Session state
if "player_df" not in st.session_state:
    st.session_state.player_df = None
if "my_team" not in st.session_state:
    st.session_state.my_team = []
if "opponent_main_team" not in st.session_state:
    st.session_state.opponent_main_team = []
if "h2h_my_team" not in st.session_state:
    st.session_state.h2h_my_team = []
if "opponent_team" not in st.session_state:
    st.session_state.opponent_team = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None

# Roster files
ROSTER_FILE = "my_team_roster.json"
OPPONENT_MAIN_FILE = "opponent_main_roster.json"
H2H_MY_FILE = "h2h_my_roster.json"
OPPONENT_H2H_FILE = "opponent_h2h_roster.json"

def scrape_and_process(url: str) -> pd.DataFrame:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        
        dfs = pd.read_html(StringIO(resp.text))
        if not dfs:
            raise ValueError("No tables found")
        
        df = max(dfs, key=len).copy()
        
        if len(df.columns) >= 13:
            df = df.iloc[:, :13]
        
        df.columns = ["Rank", "Player", "Team", "OB-PA", "R", "2B", "3B", "HR", "RBI", "BB", "HRF", "OBP", "TeamLink"]
        
        df["OB-PA"] = df["OB-PA"].astype(str).str.replace(r"[\*\s]", "", regex=True).str.strip()
        
        split = df["OB-PA"].str.split("-", expand=True)
        df["OB"] = pd.to_numeric(split[0], errors="coerce").fillna(0).astype(int)
        df["PA"] = pd.to_numeric(split[1], errors="coerce").fillna(0).astype(int)
        
        df["OBA"] = pd.to_numeric(df["OBP"], errors="coerce").fillna(0)
        
        numeric_cols = ["Rank", "R", "2B", "3B", "HR", "RBI", "BB", "HRF"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        
        if "Rank" in df.columns:
            df = df[pd.to_numeric(df["Rank"], errors="coerce").notna()].copy()
            df["Rank"] = df["Rank"].astype(int)
        
        df["Player"] = df["Player"].astype(str).str.replace(r'\[.*?\]\(.*?\)', '', regex=True).str.strip()
        df["Team"] = df["Team"].astype(str).str.replace(r'\[.*?\]\(.*?\)', '', regex=True).str.strip()
        
        df = df.sort_values(by="Rank").reset_index(drop=True)
        
        st.success(f"✅ Loaded {len(df)} players")
        return df
        
    except Exception as e:
        st.error(f"❌ Scraping error: {str(e)}")
        st.info("Try Refresh Live Data again.")
        return pd.DataFrame()

def load_data(force_refresh=False):
    url = st.session_state.get("custom_url", DEFAULT_URL)
    if force_refresh or st.session_state.player_df is None or st.session_state.player_df.empty:
        with st.spinner("Fetching live USSSA stats..."):
            st.session_state.player_df = scrape_and_process(url)
            st.session_state.last_refresh = datetime.now()
        if not st.session_state.player_df.empty:
            st.toast("✅ Live data refreshed!", icon="🥎")
    return st.session_state.player_df

def save_roster(file_path, team_list):
    with open(file_path, "w") as f:
        json.dump(team_list, f)

def load_roster(file_path, session_key):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            st.session_state[session_key] = json.load(f)
        st.toast(f"✅ Loaded {file_path}", icon="📂")

def calculate_totals(team_list):
    if not team_list:
        return {"R": 0, "2B": 0, "3B": 0, "HR": 0, "RBI": 0, "BB": 0, "OB": 0, "PA": 0, "OBA": 0.000}
    df = pd.DataFrame(team_list)
    totals = {
        "R": int(df["R"].sum()),
        "2B": int(df["2B"].sum()),
        "3B": int(df["3B"].sum()),
        "HR": int(df["HR"].sum()),
        "RBI": int(df["RBI"].sum()),
        "BB": int(df["BB"].sum()),
        "OB": int(df["OB"].sum()),
        "PA": int(df["PA"].sum()),
    }
    totals["OBA"] = round(totals["
