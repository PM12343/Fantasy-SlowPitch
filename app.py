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
if "h2h_my_team" not in st.session_state:
    st.session_state.h2h_my_team = []
if "opponent_team" not in st.session_state:
    st.session_state.opponent_team = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None

ROSTER_FILE = "my_team_roster.json"
H2H_MY_FILE = "h2h_my_roster.json"
OPPONENT_FILE = "opponent_roster.json"

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
    totals["OBA"] = round(totals["OB"] / totals["PA"], 3) if totals["PA"] > 0 else 0.000
    return totals

def compare_teams(my_totals, opp_totals):
    metrics = ["R", "2B", "3B", "HR", "RBI", "BB", "OBA"]
    results = []
    my_points = 0
    opp_points = 0
    
    for m in metrics:
        my_val = my_totals[m]
        opp_val = opp_totals[m]
        if my_val > opp_val:
            winner = "You"
            my_points += 1
        elif opp_val > my_val:
            winner = "Opponent"
            opp_points += 1
        else:
            winner = "Tie"
            my_points += 0.5
            opp_points += 0.5
        results.append({
            "Metric": m,
            "Your Team": my_val if m != "OBA" else f"{my_val:.3f}",
            "Opponent": opp_val if m != "OBA" else f"{opp_val:.3f}",
            "Winner": winner
        })
    return pd.DataFrame(results), my_points, opp_points

# ====================== UI ======================
st.title("🥎 USSSA Fantasy Slow-Pitch")
st.caption("12-player roster • 10-player Head-to-Head • Live USSSA stats")

with st.sidebar:
    st.header("⚙️ Settings")
    st.text_input("Stats URL", value=DEFAULT_URL, key="custom_url")
    
    st.divider()
    if st.button("Load Main 12-player Roster"):
        load_roster(ROSTER_FILE, "my_team")
    if st.button("Load My H2H Roster"):
        load_roster(H2H_MY_FILE, "h2h_my_team")
    if st.button("Load Opponent Roster"):
        load_roster(OPPONENT_FILE, "opponent_team")
    
    if st.button("Clear All Rosters"):
        for key in ["my_team", "h2h_my_team", "opponent_team"]:
            st.session_state[key] = []
        for f in [ROSTER_FILE, H2H_MY_FILE, OPPONENT_FILE]:
            if os.path.exists(f):
                os.remove(f)
        st.rerun()

tab_browser, tab_team, tab_dashboard, tab_h2h = st.tabs([
    "📋 Player Browser", 
    "👥 My Team (12)", 
    "📊 Dashboard", 
    "⚔️ Head-to-Head"
])

with tab_browser:
    df = load_data()
    if df.empty:
        st.stop()
    
    col_search, col_refresh = st.columns([4, 1])
    with col_search:
        search_term = st.text_input("🔍 Search by player or team", key="browser_search")
    with col_refresh:
        if st.button("🔄 Refresh Live Data", type="primary", use_container_width=True, key="refresh_main"):
            load_data(force_refresh=True)
            st.rerun()
    
    filtered = df
    if search_term:
        mask = (
            filtered["Player"].str.contains(search_term, case=False, na=False) |
            filtered["Team"].str.contains(search_term, case=False, na=False)
        )
        filtered = filtered[mask]
    
    st.subheader(f"Available Players ({len(filtered)}) • {12 - len(st.session_state.my_team)} spots left")
    
    display_cols = ["Rank", "Player", "Team", "OB-PA", "OB", "PA", "R", "2B", "3B", "HR", "RBI", "BB", "HRF", "OBA"]
    display_cols = [col for col in display_cols if col in filtered.columns]
    filtered_display = filtered[display_cols].copy()
    filtered_display.insert(0, "Select", False)
    
    edited = st.data_editor(
        filtered_display,
        hide_index=True,
        use_container_width=True,
        key="browser_data_editor",   # <-- Unique key added
        column_config={
            "Select": st.column_config.CheckboxColumn("Add to Team", default=False)
        }
    )
    
    selected_rows = edited[edited["Select"] == True]
    
    col_add1, col_add2 = st.columns(2)
    with col_add1:
        if st.button("➕ Add to Main 12-player Team", type="primary",
                     disabled=len(st.session_state.my_team) >= 12 or len(selected_rows) == 0,
                     key="add_main"):
            to_add = selected_rows.drop(columns=["Select"]).to_dict("records")
            added = 0
            for p in to_add:
                if len(st.session_state.my_team) < 12 and p not in st.session_state.my_team:
                    st.session_state.my_team.append(p)
                    added += 1
            save_roster(ROSTER_FILE, st.session_state.my_team)
            st.toast(f"Added {added} to main team", icon="✅")
            st.rerun()
    
    with col_add2:
        if st.button("➕ Add to My H2H Team (10 max)", 
                     disabled=len(st.session_state.h2h_my_team) >= 10 or len(selected_rows) == 0,
                     key="add_h2h_from_browser"):
            to_add = selected_rows.drop(columns=["Select"]).to_dict("records")
            added = 0
            for p in to_add:
                if len(st.session_state.h2h_my_team) < 10 and p not in st.session_state.h2h_my_team:
                    st.session_state.h2h_my_team.append(p)
                    added += 1
            save_roster(H2H_MY_FILE, st.session_state.h2h_my_team)
            st.toast(f"Added {added} to H2H team", icon="✅")
            st.rerun()

with tab_team:
    st.header("👥 My Main 12-Player Team")
    if not st.session_state.my_team:
        st.info("Go to Player Browser to add players.")
    else:
        team_df = pd.DataFrame(st.session_state.my_team)
        st.dataframe(team_df[["Rank", "Player", "Team", "OB-PA", "R", "2B", "3B", "HR", "RBI", "BB", "HRF", "OBA"]],
                     use_container_width=True, hide_index=True)
        for i, player in enumerate(st.session_state.my_team):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"**{player.get('Rank','')}** • {player.get('Player','')} ({player.get('Team','')})")
            with col2:
                if st.button("🗑️ Remove", key=f"remove_main_{i}"):
                    st.session_state.my_team.pop(i)
                    save_roster(ROSTER_FILE, st.session_state.my_team)
                    st.rerun()

with tab_dashboard:
    st.header("📊 Main Team Totals")
    if not st.session_state.my_team:
        st.warning("No players yet")
    else:
        totals = calculate_totals(st.session_state.my_team)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Runs (R)", totals["R"])
        c2.metric("Doubles (2B)", totals["2B"])
        c3.metric("Triples (3B)", totals["3B"])
        c4.metric("Home Runs (HR)", totals["HR"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("RBI", totals["RBI"])
        c2.metric("Walks (BB)", totals["BB"])
        c3.metric("OB / PA", f"{totals['OB']} / {totals['PA']}")
        c4.metric("OBA", f"{totals['OBA']:.3f}")
        st.caption(f"Team size: **{len(st.session_state.my_team)}/12**")

with tab_h2h:
    st.header("⚔️ Head-to-Head Matchup (10 players each)")
    st.caption("Build two 10-player teams → winner gets 1 point per category (R, 2B, 3B, HR, RBI, BB, OBA)")
    
    df = load_data()  # ensure data is loaded
    
    col_search_h2h, _ = st.columns([4, 1])
    with col_search_h2h:
        h2h_search = st.text_input("🔍 Search by player or team (H2H)", key="h2h_search")
    
    h2h_filtered = df
    if h2h_search:
        mask = (
            h2h_filtered["Player"].str.contains(h2h_search, case=False, na=False) |
            h2h_filtered["Team"].str.contains(h2h_search, case=False, na=False)
        )
        h2h_filtered = h2
