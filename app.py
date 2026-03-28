import streamlit as st
import pandas as pd
import requests
from io import StringIO
import json
import os
from datetime import datetime

st.set_page_config(page_title="USSSA Fantasy Slow-Pitch", page_icon="🥎", layout="wide")

# USSSA theme (green/blue)
st.markdown("""

""", unsafe_allow_html=True)

DEFAULT_URL = "https://web.usssa.com/sports/ConferenceUSSSA.asp?WTD=5&SA=1&State=0&ClassID=701&RR=400&MinAB=1&SeasonID=29&StatisticType=2&Sort1=OBA&sort2=&sort3="

# Session state
if "player_df" not in st.session_state:
    st.session_state.player_df = None
if "my_team" not in st.session_state:
    st.session_state.my_team = []
if "last_refresh" not in st.session_state:
    st.session_state.last_refresh = None

ROSTER_FILE = "my_team_roster.json"

def scrape_and_process(url: str) -> pd.DataFrame:
try:
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
resp = requests.get(url, headers=headers, timeout=20)
resp.raise_for_status()

# Explicitly try lxml first, fallback to html5lib
dfs = pd.read_html(StringIO(resp.text), flavor=['lxml', 'html5lib'])
df = dfs[0]

if len(df.columns) > 12:
df = df.iloc[:, :12].copy()

df.columns = ["Rank", "Player", "Team", "OB-PA", "R", "2B", "3B", "HR", "RBI", "BB", "HRF", "OBA"]

df["OB-PA"] = df["OB-PA"].astype(str).str.replace(r"[\*\s]", "", regex=True).str.strip()

split = df["OB-PA"].str.split("-", expand=True)
df["OB"] = pd.to_numeric(split[0], errors="coerce").fillna(0)
df["PA"] = pd.to_numeric(split[1], errors="coerce").fillna(0)

numeric_cols = ["Rank", "R", "2B", "3B", "HR", "RBI", "BB", "HRF", "OBA"]
for col in numeric_cols:
df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

return df.sort_values("Rank").reset_index(drop=True)
except Exception as e:
st.error(f"❌ Scraping error: {str(e)}")
st.info("Tip: Make sure lxml is in requirements.txt")
return pd.DataFrame()
def load_data(force_refresh=False):
    url = st.session_state.get("custom_url", DEFAULT_URL)
    if force_refresh or st.session_state.player_df is None or st.session_state.player_df.empty:
        with st.spinner("Fetching live USSSA stats..."):
            st.session_state.player_df = scrape_and_process(url)
            st.session_state.last_refresh = datetime.now()
        st.toast("✅ Live data refreshed!", icon="🥎")
    return st.session_state.player_df

def save_roster():
    with open(ROSTER_FILE, "w") as f:
        json.dump(st.session_state.my_team, f)

def load_saved_roster():
    if os.path.exists(ROSTER_FILE):
        with open(ROSTER_FILE, "r") as f:
            st.session_state.my_team = json.load(f)
        st.toast("✅ Saved roster loaded!", icon="📂")

# UI
st.title("🥎 USSSA Fantasy Slow-Pitch")
st.caption("Build your 12-player roster • Live stats from the official USSSA Conference page")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    st.text_input("Stats URL (change SeasonID, ClassID, etc. for other seasons)", 
                  value=DEFAULT_URL, key="custom_url")
    if st.button("Load Saved Roster"):
        load_saved_roster()
    if st.button("Clear My Team"):
        st.session_state.my_team = []
        if os.path.exists(ROSTER_FILE):
            os.remove(ROSTER_FILE)
        st.rerun()

tab_browser, tab_team, tab_dashboard = st.tabs(["📋 Player Browser", "👥 My Team", "📊 Team Dashboard"])

with tab_browser:
    df = load_data()
    if df.empty:
        st.stop()
    
    col_search, col_refresh = st.columns([4, 1])
    with col_search:
        search_term = st.text_input("🔍 Search player or team", "")
    with col_refresh:
        if st.button("🔄 Refresh Live Data", type="primary", use_container_width=True):
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
    
    # Add checkbox column for easy selection
    display_cols = ["Rank", "Player", "Team", "OB-PA", "OB", "PA", "R", "2B", "3B", "HR", "RBI", "BB", "HRF", "OBA"]
    filtered_display = filtered[display_cols].copy()
    filtered_display.insert(0, "Select", False)
    
    edited = st.data_editor(
        filtered_display,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Select": st.column_config.CheckboxColumn("Add to Team", default=False),
            "OB-PA": st.column_config.TextColumn("OB-PA"),
            "OBA": st.column_config.NumberColumn("OBA", format="%.3f"),
        },
        num_rows="fixed"
    )
    
    selected_rows = edited[edited["Select"] == True]
    
    if st.button("➕ Add Selected Players", type="primary", disabled=len(st.session_state.my_team) >= 12 or len(selected_rows) == 0):
        to_add = selected_rows.drop(columns=["Select"]).to_dict("records")
        for player in to_add:
            if len(st.session_state.my_team) < 12 and player not in st.session_state.my_team:
                st.session_state.my_team.append(player)
        save_roster()
        st.toast(f"Added {len(to_add)} player(s)!", icon="✅")
        st.rerun()

with tab_team:
    st.header("👥 My Team")
    if not st.session_state.my_team:
        st.info("Your roster is empty. Go to Player Browser to add players.")
    else:
        team_df = pd.DataFrame(st.session_state.my_team)
        st.dataframe(
            team_df[["Rank", "Player", "Team", "OB-PA", "OB", "PA", "R", "2B", "3B", "HR", "RBI", "BB", "HRF", "OBA"]],
            use_container_width=True,
            hide_index=True
        )
        
        # Remove buttons
        for i, player in enumerate(st.session_state.my_team):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.write(f"**{player['Rank']}** • {player['Player']} ({player['Team']})")
            with col2:
                if st.button("🗑️ Remove", key=f"remove_{i}"):
                    st.session_state.my_team.pop(i)
                    save_roster()
                    st.rerun()

with tab_dashboard:
    st.header("📊 Real-Time Team Totals")
    if len(st.session_state.my_team) == 0:
        st.warning("No players yet — totals will appear once you build your roster.")
    else:
        team_df = pd.DataFrame(st.session_state.my_team)
        
        totals = {
            "R": team_df["R"].sum(),
            "2B": team_df["2B"].sum(),
            "3B": team_df["3B"].sum(),
            "HR": team_df["HR"].sum(),
            "RBI": team_df["RBI"].sum(),
            "BB": team_df["BB"].sum(),
            "OB": team_df["OB"].sum(),
            "PA": team_df["PA"].sum(),
        }
        totals["OBA"] = round(totals["OB"] / totals["PA"], 3) if totals["PA"] > 0 else 0.000
        
        cols = st.columns(4)
        cols[0].metric("Total Runs (R)", totals["R"])
        cols[1].metric("Doubles (2B)", totals["2B"])
        cols[2].metric("Triples (3B)", totals["3B"])
        cols[3].metric("Home Runs (HR)", totals["HR"])
        
        cols = st.columns(4)
        cols[0].metric("RBI", totals["RBI"])
        cols[1].metric("Walks (BB)", totals["BB"])
        cols[2].metric("Total OB / PA", f"{totals['OB']:,} / {totals['PA']:,}")
        cols[3].metric("Team OBA", f"{totals['OBA']:.3f} ({totals['OBA']*100:.1f}%)")
        
        st.caption(f"Team size: **{len(st.session_state.my_team)}/12** players • Last refreshed: {st.session_state.last_refresh}")

st.caption("Built as a complete fantasy layer on top of the exact USSSA stats page you provided. Fully mobile-responsive and dark-mode friendly.")
