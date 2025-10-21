import streamlit as st
import json
from datetime import datetime
import math
from collections import defaultdict

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None

# Hardcoded users (username: password, emoji)
USERS = {
    'player1': {'password': 'pass1', 'emoji': '🎯'},
    'player2': {'password': 'pass2', 'emoji': '⚡'},
    'player3': {'password': 'pass3', 'emoji': '🔥'},
    'player4': {'password': 'pass4', 'emoji': '💎'},
}

# ELO calculation function
def calculate_elo(winner_elo, loser_elo, k=32):
    """Calculate new ELO ratings after a match"""
    expected_winner = 1 / (1 + math.pow(10, (loser_elo - winner_elo) / 400))
    expected_loser = 1 / (1 + math.pow(10, (winner_elo - loser_elo) / 400))
    
    new_winner_elo = winner_elo + k * (1 - expected_winner)
    new_loser_elo = loser_elo + k * (0 - expected_loser)
    
    winner_change = round(new_winner_elo - winner_elo)
    loser_change = round(new_loser_elo - loser_elo)
    
    return round(new_winner_elo), round(new_loser_elo), winner_change, loser_change

# Initialize user data
def init_user_data():
    """Initialize all users with default ELO and stats"""
    user_data = {}
    for username in USERS.keys():
        user_data[username] = {
            'elo': 1500,
            'matches': 0,
            'wins': 0,
            'losses': 0,
            'point_diff': 0,
            'points_scored': 0,
            'points_conceded': 0,
            'current_streak': 0,  # Positive for wins, negative for losses
            'best_streak': 0,
            'worst_streak': 0
        }
    return user_data

# Calculate statistics
def calculate_stats(user_data, username):
    """Calculate advanced statistics for a player"""
    data = user_data[username]
    
    win_rate = (data['wins'] / data['matches'] * 100) if data['matches'] > 0 else 0
    avg_points_scored = data['points_scored'] / data['matches'] if data['matches'] > 0 else 0
    avg_points_conceded = data['points_conceded'] / data['matches'] if data['matches'] > 0 else 0
    
    return {
        'win_rate': win_rate,
        'avg_points_scored': avg_points_scored,
        'avg_points_conceded': avg_points_conceded,
        'current_streak': data['current_streak'],
        'best_streak': data['best_streak'],
        'worst_streak': data['worst_streak']
    }

def get_head_to_head(match_history, player1, player2):
    """Get head-to-head record between two players"""
    p1_wins = 0
    p2_wins = 0
    p1_points = 0
    p2_points = 0
    
    for match in match_history:
        if match.get('confirmed', False):
            if (match['winner'] == player1 and match['loser'] == player2):
                p1_wins += 1
                p1_points += match['winner_score']
                p2_points += match['loser_score']
            elif (match['winner'] == player2 and match['loser'] == player1):
                p2_wins += 1
                p2_points += match['winner_score']
                p1_points += match['loser_score']
    
    return {
        'p1_wins': p1_wins,
        'p2_wins': p2_wins,
        'p1_points': p1_points,
        'p2_points': p2_points,
        'total_matches': p1_wins + p2_wins
    }

# Load data from storage
def load_data():
    """Load user data, pending matches, and match history from JSON files"""
    try:
        with open('user_data.json', 'r') as f:
            user_data = json.load(f)
    except FileNotFoundError:
        user_data = init_user_data()
        save_user_data(user_data)
    
    try:
        with open('pending_matches.json', 'r') as f:
            pending_matches = json.load(f)
    except FileNotFoundError:
        pending_matches = []
    
    try:
        with open('match_history.json', 'r') as f:
            match_history = json.load(f)
    except FileNotFoundError:
        match_history = []
    
    return user_data, pending_matches, match_history

# Save data to storage
def save_data(user_data, pending_matches, match_history):
    """Save all data to JSON files"""
    save_user_data(user_data)
    
    with open('pending_matches.json', 'w') as f:
        json.dump(pending_matches, f, indent=2)
    
    with open('match_history.json', 'w') as f:
        json.dump(match_history, f, indent=2)

def save_user_data(user_data):
    """Save user data to JSON file"""
    with open('user_data.json', 'w') as f:
        json.dump(user_data, f, indent=2)

def update_streak(user_data, username, won):
    """Update win/loss streak for a player"""
    current = user_data[username]['current_streak']
    
    if won:
        if current >= 0:
            user_data[username]['current_streak'] = current + 1
        else:
            user_data[username]['current_streak'] = 1
    else:
        if current <= 0:
            user_data[username]['current_streak'] = current - 1
        else:
            user_data[username]['current_streak'] = -1
    
    # Update best/worst streaks
    new_streak = user_data[username]['current_streak']
    if new_streak > user_data[username]['best_streak']:
        user_data[username]['best_streak'] = new_streak
    if new_streak < user_data[username]['worst_streak']:
        user_data[username]['worst_streak'] = new_streak

# Login page
def login_page():
    st.markdown("""
        <style>
        .login-container {
            max-width: 400px;
            margin: 0 auto;
            padding: 2rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.title("🏓 Ping Pong Leaderboard")
    st.subheader("Login")
    
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login", use_container_width=True):
        if username in USERS and USERS[username]['password'] == password:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.rerun()
        else:
            st.error("❌ Invalid credentials")

# Submit match page
def submit_match_page(user_data, pending_matches, match_history):
    st.subheader("📝 Submit Match Result")
    
    # Check for pending confirmations for current user
    user_pending = [m for m in pending_matches if m['confirmer'] == st.session_state.username]
    
    if user_pending:
        st.warning(f"⏳ **{len(user_pending)} match(es) awaiting your confirmation**")
        
        for match in user_pending:
            with st.container():
                st.markdown(f"""
                    <div style='background-color: #f0f2f6; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;'>
                        <h4>{USERS[match['winner']]['emoji']} {match['winner']} defeated {USERS[match['loser']]['emoji']} {match['loser']}</h4>
                        <p><strong>Score:</strong> {match['winner_score']} - {match['loser_score']}</p>
                        <p><strong>Submitted by:</strong> {match['submitter']}</p>
                    </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Confirm", key=f"confirm_{match['id']}", use_container_width=True):
                        process_confirmed_match(match, user_data, match_history)
                        pending_matches.remove(match)
                        save_data(user_data, pending_matches, match_history)
                        st.success("✅ Match confirmed!")
                        st.rerun()
                
                with col2:
                    if st.button("❌ Reject", key=f"reject_{match['id']}", use_container_width=True):
                        pending_matches.remove(match)
                        save_data(user_data, pending_matches, match_history)
                        st.info("Match rejected")
                        st.rerun()
                
                st.divider()
    
    # Submit new match
    st.markdown("### 🎮 Submit New Match")
    
    other_players = [p for p in USERS.keys() if p != st.session_state.username]
    opponent = st.selectbox("Opponent", other_players, format_func=lambda x: f"{USERS[x]['emoji']} {x}")
    
    col1, col2 = st.columns(2)
    with col1:
        your_score = st.number_input(f"{USERS[st.session_state.username]['emoji']} Your Score", min_value=0, value=11, step=1)
    with col2:
        opponent_score = st.number_input(f"{USERS[opponent]['emoji']} Opponent Score", min_value=0, value=9, step=1)
    
    if st.button("Submit Match", use_container_width=True, type="primary"):
        if your_score == opponent_score:
            st.error("❌ Scores cannot be tied")
        else:
            winner = st.session_state.username if your_score > opponent_score else opponent
            loser = opponent if your_score > opponent_score else st.session_state.username
            winner_score = max(your_score, opponent_score)
            loser_score = min(your_score, opponent_score)
            
            match = {
                'id': datetime.now().isoformat(),
                'winner': winner,
                'loser': loser,
                'winner_score': winner_score,
                'loser_score': loser_score,
                'submitter': st.session_state.username,
                'confirmer': opponent,
                'timestamp': datetime.now().isoformat()
            }
            
            pending_matches.append(match)
            save_data(user_data, pending_matches, match_history)
            st.success(f"✅ Match submitted! Waiting for {opponent} to confirm.")
            st.rerun()

def process_confirmed_match(match, user_data, match_history):
    """Process a confirmed match and update ELO ratings"""
    winner = match['winner']
    loser = match['loser']
    
    # Calculate new ELOs with changes
    new_winner_elo, new_loser_elo, winner_change, loser_change = calculate_elo(
        user_data[winner]['elo'],
        user_data[loser]['elo']
    )
    
    # Store ELO changes in match
    match['winner_elo_change'] = winner_change
    match['loser_elo_change'] = loser_change
    match['winner_old_elo'] = user_data[winner]['elo']
    match['loser_old_elo'] = user_data[loser]['elo']
    
    # Update winner stats
    user_data[winner]['elo'] = new_winner_elo
    user_data[winner]['matches'] += 1
    user_data[winner]['wins'] += 1
    user_data[winner]['point_diff'] += (match['winner_score'] - match['loser_score'])
    user_data[winner]['points_scored'] += match['winner_score']
    user_data[winner]['points_conceded'] += match['loser_score']
    update_streak(user_data, winner, True)
    
    # Update loser stats
    user_data[loser]['elo'] = new_loser_elo
    user_data[loser]['matches'] += 1
    user_data[loser]['losses'] += 1
    user_data[loser]['point_diff'] -= (match['winner_score'] - match['loser_score'])
    user_data[loser]['points_scored'] += match['loser_score']
    user_data[loser]['points_conceded'] += match['winner_score']
    update_streak(user_data, loser, False)
    
    # Add to history
    match['confirmed'] = True
    match_history.insert(0, match)

# Leaderboard page
def leaderboard_page(user_data):
    st.subheader("🏆 Leaderboard")
    
    # Sort by ELO
    sorted_players = sorted(user_data.items(), key=lambda x: x[1]['elo'], reverse=True)
    
    # Display leaderboard with enhanced stats
    for idx, (username, data) in enumerate(sorted_players, 1):
        stats = calculate_stats(user_data, username)
        
        # Create card for each player
        with st.container():
            # Rank and medal
            medal = ""
            if idx == 1:
                medal = "🥇"
            elif idx == 2:
                medal = "🥈"
            elif idx == 3:
                medal = "🥉"
            
            # Header row
            col1, col2, col3, col4 = st.columns([1, 3, 2, 2])
            
            with col1:
                st.markdown(f"<h2 style='margin:0'>{medal if medal else idx}</h2>", unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"<h3 style='margin:0'>{USERS[username]['emoji']} {username}</h3>", unsafe_allow_html=True)
            
            with col3:
                st.metric("ELO Rating", data['elo'])
            
            with col4:
                win_rate_color = "green" if stats['win_rate'] >= 50 else "red"
                st.markdown(f"<div style='text-align:center'><p style='margin:0; color:gray'>Win Rate</p><p style='margin:0; font-size:1.5rem; color:{win_rate_color}'>{stats['win_rate']:.1f}%</p></div>", unsafe_allow_html=True)
            
            # Stats row
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.markdown(f"**W/L:** {data['wins']}/{data['losses']}")
            
            with col2:
                diff_color = "green" if data['point_diff'] >= 0 else "red"
                st.markdown(f"**PD:** :{diff_color}[{data['point_diff']:+d}]")
            
            with col3:
                st.markdown(f"**Avg Scored:** {stats['avg_points_scored']:.1f}")
            
            with col4:
                st.markdown(f"**Avg Conceded:** {stats['avg_points_conceded']:.1f}")
            
            with col5:
                streak = stats['current_streak']
                if streak > 0:
                    st.markdown(f"**Streak:** :green[🔥 W{streak}]")
                elif streak < 0:
                    st.markdown(f"**Streak:** :red[❄️ L{abs(streak)}]")
                else:
                    st.markdown(f"**Streak:** -")
            
            st.divider()

# Player stats page
def player_stats_page(user_data, match_history):
    st.subheader("📊 Player Statistics")
    
    selected_player = st.selectbox(
        "Select Player", 
        list(USERS.keys()),
        format_func=lambda x: f"{USERS[x]['emoji']} {x}"
    )
    
    data = user_data[selected_player]
    stats = calculate_stats(user_data, selected_player)
    
    # Overview metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("ELO Rating", data['elo'])
    
    with col2:
        st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
    
    with col3:
        st.metric("Total Matches", data['matches'])
    
    with col4:
        st.metric("Point Difference", data['point_diff'], 
                 delta_color="normal" if data['point_diff'] >= 0 else "inverse")
    
    st.divider()
    
    # Detailed stats
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 Performance")
        st.markdown(f"**Wins:** {data['wins']}")
        st.markdown(f"**Losses:** {data['losses']}")
        st.markdown(f"**Points Scored:** {data['points_scored']}")
        st.markdown(f"**Points Conceded:** {data['points_conceded']}")
        st.markdown(f"**Avg Points Scored:** {stats['avg_points_scored']:.2f}")
        st.markdown(f"**Avg Points Conceded:** {stats['avg_points_conceded']:.2f}")
    
    with col2:
        st.markdown("### 🔥 Streaks")
        
        current = stats['current_streak']
        if current > 0:
            st.markdown(f"**Current Streak:** :green[🔥 {current} wins]")
        elif current < 0:
            st.markdown(f"**Current Streak:** :red[❄️ {abs(current)} losses]")
        else:
            st.markdown(f"**Current Streak:** None")
        
        st.markdown(f"**Best Win Streak:** :green[{stats['best_streak']} wins]")
        st.markdown(f"**Worst Loss Streak:** :red[{abs(stats['worst_streak'])} losses]")
    
    st.divider()
    
    # Head-to-head records
    st.markdown("### 🤝 Head-to-Head Records")
    
    other_players = [p for p in USERS.keys() if p != selected_player]
    
    for opponent in other_players:
        h2h = get_head_to_head(match_history, selected_player, opponent)
        
        if h2h['total_matches'] > 0:
            with st.container():
                col1, col2, col3 = st.columns([2, 3, 2])
                
                with col1:
                    st.markdown(f"**{USERS[opponent]['emoji']} {opponent}**")
                
                with col2:
                    win_pct = (h2h['p1_wins'] / h2h['total_matches'] * 100) if h2h['total_matches'] > 0 else 0
                    color = "green" if win_pct >= 50 else "red"
                    st.markdown(f"**Record:** :{color}[{h2h['p1_wins']}-{h2h['p2_wins']}] ({win_pct:.0f}%)")
                
                with col3:
                    st.markdown(f"**Points:** {h2h['p1_points']}-{h2h['p2_points']}")
                
                st.divider()

# Match history page
def match_history_page(match_history):
    st.subheader("📜 Match History")
    
    if not match_history:
        st.info("No matches played yet")
        return
    
    for match in match_history[:30]:  # Show last 30 matches
        if match.get('confirmed', False):
            with st.container():
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    winner_elo_change = match.get('winner_elo_change', 0)
                    loser_elo_change = match.get('loser_elo_change', 0)
                    
                    st.markdown(f"""
                        **{USERS[match['winner']]['emoji']} {match['winner']}** defeated **{USERS[match['loser']]['emoji']} {match['loser']}**  
                        Score: **{match['winner_score']} - {match['loser_score']}** | 
                        ELO: :green[{match['winner']} +{winner_elo_change}] :red[{match['loser']} {loser_elo_change}]
                    """)
                
                with col2:
                    date_str = match['timestamp'][:10]
                    st.markdown(f"<div style='text-align:right; color:gray'>{date_str}</div>", unsafe_allow_html=True)
                
                st.divider()

# Main app
def main():
    st.set_page_config(
        page_title="Ping Pong Leaderboard", 
        page_icon="🏓", 
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Custom CSS
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
        }
        div[data-testid="stMetricValue"] {
            font-size: 1.5rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    if not st.session_state.logged_in:
        login_page()
    else:
        # Load data
        user_data, pending_matches, match_history = load_data()
        
        # Header
        st.title("🏓 Aka Ping Pong Leaderboard")
        
        # Show pending count
        user_pending_count = len([m for m in pending_matches if m['confirmer'] == st.session_state.username])
        if user_pending_count > 0:
            st.info(f"⏳ You have **{user_pending_count}** pending match confirmation(s)")
        
        # Navigation
        tab1, tab2, tab3, tab4 = st.tabs(["📝 Submit Match", "🏆 Leaderboard", "📊 Player Stats", "📜 History"])
        
        with tab1:
            submit_match_page(user_data, pending_matches, match_history)
        
        with tab2:
            leaderboard_page(user_data)
        
        with tab3:
            player_stats_page(user_data, match_history)
        
        with tab4:
            match_history_page(match_history)
        
        # Footer with logout
        st.divider()
        col1, col2, col3 = st.columns([2, 1, 2])
        with col2:
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.username = None
                st.rerun()

if __name__ == "__main__":
    main()