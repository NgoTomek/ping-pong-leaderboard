import streamlit as st
import json
from datetime import datetime
import math
from collections import defaultdict
import os
import tempfile
import shutil
import fcntl
from contextlib import contextmanager

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None

# Hardcoded users (username: password)
USERS = {
    'yankes': {'password': 'malyrobal123'},
    'janzastawa': {'password': 'janekzastawa'},
    'stasboguslawski': {'password': 'stan123'},
    'bartoszwysocki': {'password': 'haslohaslo'},
    'ngotomek': {'password': 'apexlegends'},
    'danielladny': {'password': '12345'},
    'davidg': {'password': '123456'},
    'piotreksujecki1': {'password': 'nie'},  # FIXED: Renamed to avoid duplicate
    'tomaszrymaszewski': {'password': 'tomciu123'},
    'wiktorchmielewski': {'password': 'spartagym'},
    'alexbatty': {'password': 'batty123'},
    'piotreksujecki2': {'password': 'psuja'},  # FIXED: Renamed to avoid duplicate
    'michalzajezierski': {'password': 'zajez123'},
    'mikadobrzynski': {'password': 'mika123'},
    'konradstudniarek': {'password': 'kondziks'},
    'igorzuzalek': {'password': 'zuz123'},
    'aleksandersosnowski': {'password': 'sosna123'},
    'krzysztofbaginski': {'password': 'bagieta123'},
    'lukebakicpawlak': {'password': 'bakic123'},
    'maxwilewski': {'password': 'shitatfifa'},
    'enejjancic': {'password': 'jan123'},
    'olob': {'password': 'olo123'},
    'aleksstokowski': {'password': 'stok123'},
}

# File paths
DATA_DIR = 'ping_pong_data'
USER_DATA_FILE = os.path.join(DATA_DIR, 'user_data.json')
PENDING_MATCHES_FILE = os.path.join(DATA_DIR, 'pending_matches.json')
MATCH_HISTORY_FILE = os.path.join(DATA_DIR, 'match_history.json')
LOCK_FILE = os.path.join(DATA_DIR, '.lock')

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

@contextmanager
def file_lock(lock_file_path, timeout=10):
    """Context manager for file locking to prevent race conditions"""
    lock_file = None
    try:
        lock_file = open(lock_file_path, 'w')
        # Try to acquire lock with timeout
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except (IOError, OSError) as e:
        if lock_file:
            lock_file.close()
        raise Exception("Could not acquire file lock - another operation in progress") from e
    finally:
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            except:
                pass

def atomic_write(file_path, data):
    """Write JSON data atomically to prevent corruption"""
    try:
        # Create backup if file exists
        if os.path.exists(file_path):
            backup_path = file_path + '.backup'
            shutil.copy2(file_path, backup_path)
        
        # Write to temporary file first
        temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(file_path), text=True)
        try:
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(data, f, indent=2)
            # Atomic rename (on POSIX systems)
            shutil.move(temp_path, file_path)
            return True
        except Exception as e:
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise e
    except Exception as e:
        st.error(f"Error writing to {file_path}: {str(e)}")
        # Try to restore from backup
        backup_path = file_path + '.backup'
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, file_path)
                st.warning("Restored from backup")
            except:
                pass
        return False

def validate_user_data(data):
    """Validate user data structure"""
    if not isinstance(data, dict):
        return False
    
    required_fields = ['elo', 'matches', 'wins', 'losses', 'point_diff', 
                      'points_scored', 'points_conceded', 'current_streak', 
                      'best_streak', 'worst_streak']
    
    for username, user_info in data.items():
        if not isinstance(user_info, dict):
            return False
        for field in required_fields:
            if field not in user_info:
                return False
            if not isinstance(user_info[field], (int, float)):
                return False
    
    return True

def validate_match(match):
    """Validate match data structure"""
    required_fields = ['id', 'winner', 'loser', 'winner_score', 'loser_score', 
                      'submitter', 'confirmer', 'timestamp']
    
    if not isinstance(match, dict):
        return False
    
    for field in required_fields:
        if field not in match:
            return False
    
    # Validate scores
    if not isinstance(match['winner_score'], (int, float)) or \
       not isinstance(match['loser_score'], (int, float)):
        return False
    
    if match['winner_score'] <= match['loser_score']:
        return False
    
    if match['winner_score'] < 0 or match['loser_score'] < 0:
        return False
    
    # Reasonable score limit (0-50 should cover all realistic scenarios)
    if match['winner_score'] > 50 or match['loser_score'] > 50:
        return False
    
    # Validate players exist
    if match['winner'] not in USERS or match['loser'] not in USERS:
        return False
    
    if match['winner'] == match['loser']:
        return False
    
    return True

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
            'current_streak': 0,
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

# Load data from storage with proper error handling
def load_data():
    """Load user data, pending matches, and match history from JSON files"""
    try:
        with file_lock(LOCK_FILE):
            # Load user data
            try:
                if os.path.exists(USER_DATA_FILE):
                    with open(USER_DATA_FILE, 'r') as f:
                        user_data = json.load(f)
                    
                    # Validate loaded data
                    if not validate_user_data(user_data):
                        st.warning("User data corrupted, reinitializing...")
                        user_data = init_user_data()
                        atomic_write(USER_DATA_FILE, user_data)
                    
                    # Add any new users from USERS dict
                    for username in USERS.keys():
                        if username not in user_data:
                            user_data[username] = {
                                'elo': 1500,
                                'matches': 0,
                                'wins': 0,
                                'losses': 0,
                                'point_diff': 0,
                                'points_scored': 0,
                                'points_conceded': 0,
                                'current_streak': 0,
                                'best_streak': 0,
                                'worst_streak': 0
                            }
                else:
                    user_data = init_user_data()
                    atomic_write(USER_DATA_FILE, user_data)
            except (json.JSONDecodeError, IOError) as e:
                st.error(f"Error loading user data: {str(e)}")
                user_data = init_user_data()
                atomic_write(USER_DATA_FILE, user_data)
            
            # Load pending matches
            try:
                if os.path.exists(PENDING_MATCHES_FILE):
                    with open(PENDING_MATCHES_FILE, 'r') as f:
                        pending_matches = json.load(f)
                    # Validate each match
                    pending_matches = [m for m in pending_matches if validate_match(m)]
                else:
                    pending_matches = []
            except (json.JSONDecodeError, IOError) as e:
                st.error(f"Error loading pending matches: {str(e)}")
                pending_matches = []
            
            # Load match history
            try:
                if os.path.exists(MATCH_HISTORY_FILE):
                    with open(MATCH_HISTORY_FILE, 'r') as f:
                        match_history = json.load(f)
                    # Basic validation
                    if not isinstance(match_history, list):
                        match_history = []
                else:
                    match_history = []
            except (json.JSONDecodeError, IOError) as e:
                st.error(f"Error loading match history: {str(e)}")
                match_history = []
            
            return user_data, pending_matches, match_history
    
    except Exception as e:
        st.error(f"Critical error loading data: {str(e)}")
        return init_user_data(), [], []

# Save data to storage with proper locking and error handling
def save_data(user_data, pending_matches, match_history):
    """Save all data to JSON files with atomic writes and locking"""
    try:
        with file_lock(LOCK_FILE):
            success = True
            
            # Validate before saving
            if not validate_user_data(user_data):
                st.error("Invalid user data, not saving")
                return False
            
            success &= atomic_write(USER_DATA_FILE, user_data)
            success &= atomic_write(PENDING_MATCHES_FILE, pending_matches)
            success &= atomic_write(MATCH_HISTORY_FILE, match_history)
            
            return success
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
        return False

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
            st.write(f"**{match['winner']}** defeated **{match['loser']}**")
            st.write(f"Score: {match['winner_score']} - {match['loser_score']}")
            st.write(f"Submitted by: {match['submitter']}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Confirm", key=f"confirm_{match['id']}", use_container_width=True):
                    process_confirmed_match(match, user_data, match_history)
                    pending_matches.remove(match)
                    if save_data(user_data, pending_matches, match_history):
                        st.success("✅ Match confirmed!")
                        st.rerun()
                    else:
                        st.error("Error saving data, please try again")
            
            with col2:
                if st.button("❌ Reject", key=f"reject_{match['id']}", use_container_width=True):
                    pending_matches.remove(match)
                    if save_data(user_data, pending_matches, match_history):
                        st.info("Match rejected")
                        st.rerun()
                    else:
                        st.error("Error saving data, please try again")
            
            st.divider()
    
    # Submit new match
    st.write("### Submit New Match")
    
    other_players = [p for p in USERS.keys() if p != st.session_state.username]
    opponent = st.selectbox("Opponent", other_players)
    
    col1, col2 = st.columns(2)
    with col1:
        your_score = st.number_input("Your Score", min_value=0, max_value=50, value=11, step=1)
    with col2:
        opponent_score = st.number_input("Opponent Score", min_value=0, max_value=50, value=9, step=1)
    
    if st.button("Submit Match", use_container_width=True, type="primary"):
        # Validation
        if your_score == opponent_score:
            st.error("❌ Scores cannot be tied")
        elif your_score == 0 and opponent_score == 0:
            st.error("❌ Both scores cannot be zero")
        else:
            winner = st.session_state.username if your_score > opponent_score else opponent
            loser = opponent if your_score > opponent_score else st.session_state.username
            winner_score = max(your_score, opponent_score)
            loser_score = min(your_score, opponent_score)
            
            match = {
                'id': datetime.now().isoformat(),
                'winner': winner,
                'loser': loser,
                'winner_score': int(winner_score),
                'loser_score': int(loser_score),
                'submitter': st.session_state.username,
                'confirmer': opponent,
                'timestamp': datetime.now().isoformat()
            }
            
            # Validate match before adding
            if validate_match(match):
                pending_matches.append(match)
                if save_data(user_data, pending_matches, match_history):
                    st.success(f"✅ Match submitted! Waiting for {opponent} to confirm.")
                    st.rerun()
                else:
                    st.error("Error saving match, please try again")
            else:
                st.error("Invalid match data, please check your inputs")

def process_confirmed_match(match, user_data, match_history):
    """Process a confirmed match and update ELO ratings"""
    winner = match['winner']
    loser = match['loser']
    
    # Validate players exist in user_data
    if winner not in user_data or loser not in user_data:
        st.error("Error: One or both players not found in database")
        return
    
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
    
    # Display leaderboard
    for idx, (username, data) in enumerate(sorted_players, 1):
        stats = calculate_stats(user_data, username)
        
        col1, col2, col3, col4, col5, col6 = st.columns([1, 2, 2, 2, 2, 2])
        
        with col1:
            if idx == 1:
                st.write("🥇")
            elif idx == 2:
                st.write("🥈")
            elif idx == 3:
                st.write("🥉")
            else:
                st.write(f"**{idx}**")
        
        with col2:
            st.write(f"**{username}**")
        
        with col3:
            st.write(f"ELO: **{data['elo']}**")
        
        with col4:
            st.write(f"W/L: {data['wins']}/{data['losses']}")
        
        with col5:
            diff_color = "green" if data['point_diff'] >= 0 else "red"
            st.write(f"PD: :{diff_color}[**{data['point_diff']:+d}**]")
        
        with col6:
            win_rate_color = "green" if stats['win_rate'] >= 50 else "red"
            st.write(f"WR: :{win_rate_color}[**{stats['win_rate']:.1f}%**]")
        
        st.divider()

# Player stats page
def player_stats_page(user_data, match_history):
    st.subheader("📊 Player Statistics")
    
    selected_player = st.selectbox(
        "Select Player", 
        list(USERS.keys())
    )
    
    if selected_player not in user_data:
        st.error("Player data not found")
        return
    
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
        st.write("### 🎯 Performance")
        st.write(f"**Wins:** {data['wins']}")
        st.write(f"**Losses:** {data['losses']}")
        st.write(f"**Points Scored:** {data['points_scored']}")
        st.write(f"**Points Conceded:** {data['points_conceded']}")
        st.write(f"**Avg Points Scored:** {stats['avg_points_scored']:.2f}")
        st.write(f"**Avg Points Conceded:** {stats['avg_points_conceded']:.2f}")
    
    with col2:
        st.write("### 🔥 Streaks")
        
        current = stats['current_streak']
        if current > 0:
            st.write(f"**Current Streak:** :green[🔥 {current} wins]")
        elif current < 0:
            st.write(f"**Current Streak:** :red[❄️ {abs(current)} losses]")
        else:
            st.write(f"**Current Streak:** None")
        
        st.write(f"**Best Win Streak:** :green[{stats['best_streak']} wins]")
        st.write(f"**Worst Loss Streak:** :red[{abs(stats['worst_streak'])} losses]")
    
    st.divider()
    
    # Head-to-head records
    st.write("### 🤝 Head-to-Head Records")
    
    other_players = [p for p in USERS.keys() if p != selected_player]
    
    for opponent in other_players:
        h2h = get_head_to_head(match_history, selected_player, opponent)
        
        if h2h['total_matches'] > 0:
            col1, col2, col3 = st.columns([2, 3, 2])
            
            with col1:
                st.write(f"**{opponent}**")
            
            with col2:
                win_pct = (h2h['p1_wins'] / h2h['total_matches'] * 100) if h2h['total_matches'] > 0 else 0
                color = "green" if win_pct >= 50 else "red"
                st.write(f"Record: :{color}[{h2h['p1_wins']}-{h2h['p2_wins']}] ({win_pct:.0f}%)")
            
            with col3:
                st.write(f"Points: {h2h['p1_points']}-{h2h['p2_points']}")
            
            st.divider()

# Match history page
def match_history_page(match_history):
    st.subheader("📜 Match History")
    
    if not match_history:
        st.info("No matches played yet")
        return
    
    for match in match_history[:30]:  # Show last 30 matches
        if match.get('confirmed', False):
            winner_elo_change = match.get('winner_elo_change', 0)
            loser_elo_change = match.get('loser_elo_change', 0)
            
            st.write(f"**{match['winner']}** defeated **{match['loser']}**")
            st.write(f"Score: {match['winner_score']} - {match['loser_score']} | ELO: :green[{match['winner']} +{winner_elo_change}] :red[{match['loser']} {loser_elo_change}]")
            
            # FIXED: Added safe timestamp handling
            timestamp = match.get('timestamp', 'Unknown date')
            if timestamp and timestamp != 'Unknown date':
                try:
                    st.write(f"Date: {timestamp[:10]}")
                except:
                    st.write(f"Date: {timestamp}")
            else:
                st.write("Date: Unknown")
            
            st.divider()

# Main app
def main():
    st.set_page_config(
        page_title="Ping Pong Leaderboard", 
        page_icon="🏓", 
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # Custom CSS for mobile-friendly UI
    st.markdown("""
        <style>
        .stButton>button {
            width: 100%;
        }
        </style>
    """, unsafe_allow_html=True)
    
    if not st.session_state.logged_in:
        login_page()
    else:
        # Load data
        user_data, pending_matches, match_history = load_data()
        
        # Header
        st.title("🏓 Ping Pong Leaderboard")
        
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
