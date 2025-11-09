import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import datetime, date
from site_info import site_information
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from streamlit_plotly_events import plotly_events

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="Water Quality Dashboard",
    page_icon="💧",
    layout="wide"
)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize Supabase
@st.cache_resource
def init_supabase():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)

supabase = init_supabase()

# Admin email - only this user can manage sites
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "megandaiger@gmail.com")

def is_admin(email):
    """Check if user is admin"""
    # Check env-configured admin
    if email == ADMIN_EMAIL:
        return True
    
    # Check if user has been approved in pending_admins table
    try:
        approved_response = supabase.table('pending_admins').select("email").eq('email', email).eq('status', 'approved').execute()
        if approved_response.data:
            return True
    except:
        pass  # If table doesn't exist yet, just use hardcoded list
    
    return False

def send_admin_notification_email(new_user_email):
    """Send email notification to admin when new user requests access"""
    try:
        # Email configuration - you'll need to set these environment variables
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        sender_email = os.getenv("ADMIN_EMAIL", "megandaiger@gmail.com")
        sender_password = os.getenv("EMAIL_PASSWORD")  # App password for Gmail
        
        if not sender_password:
            st.warning("Email notification not configured. Please set EMAIL_PASSWORD environment variable.")
            return
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = sender_email  # Send to yourself
        msg['Subject'] = "New Admin Access Request - Water Quality Dashboard"
        
        body = f"""
        A new user has requested admin access to the Water Quality Dashboard:
        
        Email: {new_user_email}
        Requested at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        To approve this user:
        1. Log into your dashboard as admin
        2. Go to the "Manage Sites" tab
        3. Find the pending approval section
        4. Approve or deny the request
        
        Dashboard URL: [Your deployed URL here]
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, sender_email, text)
        server.quit()
        
    except Exception as e:
        st.error(f"Failed to send notification email: {str(e)}")

def get_sites():
    """Get all sites from database or return default sites"""
    try:
        response = supabase.table('sites').select("*").execute()
        if response.data:
            return [(site['full_name'], site['short_name']) for site in response.data]
        else:
            # Return default sites if no sites table exists
            return [
                ("Blue River at Silverthorne Pavilion- 196", "Blue River"),
                ("Snake River KSS- 52", "Snake River"), 
                ("Swan River Reach A- 1007", "Swan River")
            ]
    except:
        # Fallback to hardcoded sites if sites table doesn't exist
        return [
            ("Blue River at Silverthorne Pavilion- 196", "Blue River"),
            ("Snake River KSS- 52", "Snake River"), 
            ("Swan River Reach A- 1007", "Swan River")
        ]

def edit_data():
    """Admin interface for editing existing data"""
    
    st.info("💡 Click a data entry to edit or delete")
    
    try:
        # Fetch all data with ID for editing
        response = supabase.table('water_quality').select("*").order('date', desc=True).execute()
        df = pd.DataFrame(response.data)
        
        if not df.empty:
            # Convert date column to datetime for display
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%m/%d/%Y')
            
            # Create abbreviated site names for display
            sites = get_sites()
            site_mapping = {full_name: short_name for full_name, short_name in sites}
            site_mapping.update({
                'Site 1': 'Blue River',
                'Site 2': 'Snake River', 
                'Site 3': 'Swan River'
            })
            df['site_display'] = df['site'].map(site_mapping)
            
            st.subheader("Existing Data Entries")
            
            # Display data in a table with edit buttons
            for idx, row in df.iterrows():
                with st.expander(f"{row['site_display']} - {row['date']} (ID: {row['id']})"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.write(f"**Site:** {row['site_display']}")
                        st.write(f"**Date:** {row['date']}")
                        st.write(f"**Dissolved Oxygen:** {row['dissolved_oxygen_mg']} mg/L ({row['dissolved_oxygen_sat']}% sat)")
                        st.write(f"**Hardness:** {row['hardness']} mg/L CaCO3")
                        st.write(f"**Alkalinity:** {row['alkalinity']} mg/L CaCO3")
                        st.write(f"**pH:** {row['ph']}")
                        st.write(f"**Temperature:** {row['temperature']}°C")
                        st.write(f"**Flow:** {row['flow']} cfs")
                        if row['notes']:
                            st.write(f"**Notes:** {row['notes']}")
                    
                    with col2:
                        if st.button("Edit", key=f"edit_data_{row['id']}"):
                            st.session_state[f'editing_data_{row["id"]}'] = True
                            st.rerun()
                        
                        if st.button("Delete", key=f"delete_data_{row['id']}"):
                            if st.session_state.get(f'confirm_delete_{row["id"]}', False):
                                # Delete the record
                                supabase.table('water_quality').delete().eq('id', row['id']).execute()
                                st.success("Data deleted!")
                                st.rerun()
                            else:
                                st.session_state[f'confirm_delete_{row["id"]}'] = True
                                st.warning("Click Delete again to confirm")
                                st.rerun()
            
            # Edit forms for each data entry
            for idx, row in df.iterrows():
                if st.session_state.get(f'editing_data_{row["id"]}', False):
                    st.subheader(f"Edit Entry: {row['site_display']} - {row['date']}")
                    
                    with st.form(f"edit_form_{row['id']}"):
                        # Site selection
                        sites = get_sites()
                        site_options = [full_name for full_name, short_name in sites]
                        
                        # Find current site index
                        current_site_idx = 0
                        for i, (full_name, short_name) in enumerate(sites):
                            if row['site'] == full_name or (row['site'] in ['Site 1', 'Site 2', 'Site 3'] and 
                                                          site_mapping.get(row['site']) == short_name):
                                current_site_idx = i
                                break
                        
                        new_site = st.selectbox("Site", site_options, index=current_site_idx)
                        new_date = st.date_input("Date", value=pd.to_datetime(row['date']).date())
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            # Dissolved Oxygen (mg/L)
                            existing_do_mg = row['dissolved_oxygen_mg']
                            col_input, col_checkbox = st.columns([3, 1])
                            with col_checkbox:
                                st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                                do_mg_not_available = st.checkbox("N/A", 
                                                                value=existing_do_mg is None, 
                                                                key=f"edit_do_mg_not_available_{row['id']}",
                                                                help="Check if no measurement was taken")
                                st.markdown('</div>', unsafe_allow_html=True)
                            with col_input:
                                if do_mg_not_available:
                                    st.text_input("Dissolved Oxygen (mg/L)", value="Data not available", disabled=True, key=f"edit_do_mg_disabled_{row['id']}")
                                    do_mg = None
                                else:
                                    do_mg = st.number_input("Dissolved Oxygen (mg/L)", 
                                                          value=float(existing_do_mg) if existing_do_mg is not None else 0.0, 
                                                          format="%.2f", key=f"edit_do_mg_input_{row['id']}")
                            
                            # Dissolved Oxygen (% saturation)
                            existing_do_sat = row['dissolved_oxygen_sat']
                            col_input, col_checkbox = st.columns([3, 1])
                            with col_input:
                                dissolved_oxygen_sat = st.number_input("Dissolved Oxygen (% saturation)", 
                                                                     value=float(existing_do_sat) if existing_do_sat is not None else 0.0, 
                                                                     format="%.1f", key=f"edit_do_sat_input_{row['id']}")
                            with col_checkbox:
                                st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                                do_sat_not_available = st.checkbox("N/A", 
                                                                 value=existing_do_sat is None, 
                                                                 key=f"edit_do_sat_not_available_{row['id']}",
                                                                 help="Check if no measurement was taken")
                                st.markdown('</div>', unsafe_allow_html=True)
                            if do_sat_not_available:
                                do_sat = None
                            else:
                                do_sat = dissolved_oxygen_sat
                            
                            # Hardness
                            existing_hardness = row['hardness']
                            col_input, col_checkbox = st.columns([3, 1])
                            with col_checkbox:
                                st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                                hardness_not_available = st.checkbox("N/A", 
                                                                    value=existing_hardness is None, 
                                                                    key=f"edit_hardness_not_available_{row['id']}",
                                                                    help="Check if no measurement was taken")
                                st.markdown('</div>', unsafe_allow_html=True)
                            with col_input:
                                if hardness_not_available:
                                    st.text_input("Hardness (mg/L CaCO3)", value="Data not available", disabled=True, key=f"edit_hardness_disabled_{row['id']}")
                                    hardness = None
                                else:
                                    hardness = st.number_input("Hardness (mg/L CaCO3)", 
                                                             value=float(existing_hardness) if existing_hardness is not None else 0.0, 
                                                             format="%.1f", key=f"edit_hardness_input_{row['id']}")
                            
                            # Alkalinity
                            existing_alkalinity = row['alkalinity']
                            col_input, col_checkbox = st.columns([3, 1])
                            with col_input:
                                alkalinity_value = st.number_input("Alkalinity (mg/L CaCO3)", 
                                                                 value=float(existing_alkalinity) if existing_alkalinity is not None else 0.0, 
                                                                 format="%.1f", key=f"edit_alkalinity_input_{row['id']}")
                            with col_checkbox:
                                st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                                alkalinity_not_available = st.checkbox("N/A", 
                                                                      value=existing_alkalinity is None, 
                                                                      key=f"edit_alkalinity_not_available_{row['id']}",
                                                                      help="Check if no measurement was taken")
                                st.markdown('</div>', unsafe_allow_html=True)
                            if alkalinity_not_available:
                                alkalinity = None
                            else:
                                alkalinity = alkalinity_value
                        
                        with col2:
                            # pH
                            existing_ph = row['ph']
                            col_input, col_checkbox = st.columns([3, 1])
                            with col_input:
                                ph_value = st.number_input("pH (S.U.s)", 
                                                         value=float(existing_ph) if existing_ph is not None else 7.0, 
                                                         format="%.1f", key=f"edit_ph_input_{row['id']}")
                            with col_checkbox:
                                st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                                ph_not_available = st.checkbox("N/A", 
                                                              value=existing_ph is None, 
                                                              key=f"edit_ph_not_available_{row['id']}",
                                                              help="Check if no measurement was taken")
                                st.markdown('</div>', unsafe_allow_html=True)
                            if ph_not_available:
                                ph = None
                            else:
                                ph = ph_value
                            
                            # Temperature
                            existing_temp = row['temperature']
                            col_input, col_checkbox = st.columns([3, 1])
                            with col_checkbox:
                                st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                                temp_not_available = st.checkbox("N/A", 
                                                                value=existing_temp is None, 
                                                                key=f"edit_temp_not_available_{row['id']}",
                                                                help="Check if no measurement was taken")
                                st.markdown('</div>', unsafe_allow_html=True)
                            with col_input:
                                if temp_not_available:
                                    st.text_input("Temperature (°C)", value="Data not available", disabled=True, key=f"edit_temp_disabled_{row['id']}")
                                    temp = None
                                else:
                                    temp = st.number_input("Temperature (°C)", 
                                                         value=float(existing_temp) if existing_temp is not None else 0.0, 
                                                         format="%.1f", key=f"edit_temp_input_{row['id']}")
                            
                            # Flow
                            existing_flow = row['flow']
                            col_input, col_checkbox = st.columns([3, 1])
                            with col_input:
                                flow_value = st.number_input("Flow (cfs)", 
                                                           value=float(existing_flow) if existing_flow is not None else 0.0, 
                                                           format="%.2f", key=f"edit_flow_input_{row['id']}")
                            with col_checkbox:
                                st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                                flow_not_available = st.checkbox("N/A", 
                                                                value=existing_flow is None, 
                                                                key=f"edit_flow_not_available_{row['id']}",
                                                                help="Check if no measurement was taken")
                                st.markdown('</div>', unsafe_allow_html=True)
                            if flow_not_available:
                                flow = None
                            else:
                                flow = flow_value
                            
                            notes = st.text_area("Notes", value=row['notes'] if row['notes'] else "")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.form_submit_button("💾 Save Changes", type="primary"):
                                # Map site name for database
                                site_name_mapping = {
                                    'Blue River at Silverthorne Pavilion- 196': 'Site 1',
                                    'Snake River KSS- 52': 'Site 2',
                                    'Swan River Reach A- 1007': 'Site 3'
                                }
                                db_site_name = site_name_mapping.get(new_site, new_site)
                                
                                # Update data in database
                                update_data = {
                                    'site': db_site_name,
                                    'date': str(new_date),
                                    'dissolved_oxygen_mg': do_mg,
                                    'dissolved_oxygen_sat': do_sat,
                                    'hardness': hardness,
                                    'alkalinity': alkalinity,
                                    'ph': ph,
                                    'temperature': temp,
                                    'flow': flow,
                                    'notes': notes
                                }
                                
                                supabase.table('water_quality').update(update_data).eq('id', row['id']).execute()
                                st.success("Data updated successfully!")
                                st.session_state[f'editing_data_{row["id"]}'] = False
                                
                                # Clear cache so graphs update
                                if hasattr(st, 'cache_data'):
                                    st.cache_data.clear()
                                if hasattr(st, 'cache_resource'):
                                    st.cache_resource.clear()
                                
                                st.rerun()
                        
                        with col2:
                            if st.form_submit_button("❌ Cancel"):
                                st.session_state[f'editing_data_{row["id"]}'] = False
                                st.rerun()
        
        else:
            st.info("No data entries found.")
            
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")

def manage_sites(is_user_admin):
    """Admin interface for managing sites"""
    st.header("🔧 Site Management (Admin Only)")
    st.info("💡 Edit site information including names, coordinates, descriptions, and elevation data")
    
    # Load sites from database
    try:
        response = supabase.table('sites').select("*").order('site_number').execute()
        sites_from_db = response.data
        
        # Convert to the format expected by the UI
        sites_data = {}
        for site in sites_from_db:
            # Null-safe parsing for coordinates
            def _to_float(val):
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return 0.0
            sites_data[site['full_name']] = {
                'id': site.get('id'),
                'site_number': site.get('site_number'),
                'short_name': site.get('short_name'),
                'latitude': _to_float(site.get('latitude')),
                'longitude': _to_float(site.get('longitude')),
                'elevation': site.get('elevation'),
                'description': site.get('description')
            }
    except Exception as e:
        st.error(f"Error loading sites from database: {str(e)}")
        # Fallback to hardcoded data if database fails
        sites_data = {
            'Blue River at Silverthorne Pavilion- 196': {
                'id': None,
                'site_number': 196,
                'short_name': 'Blue River',
                'latitude': 39.6297,
                'longitude': -106.0711,
                'elevation': 9035,
                'description': 'Located at Silverthorne Pavilion, this site monitors the Blue River as it flows through the town of Silverthorne.'
            },
            'Snake River KSS- 52': {
                'id': None,
                'site_number': 52,
                'short_name': 'Snake River',
                'latitude': 39.6123,
                'longitude': -106.0856,
                'elevation': 9150,
                'description': 'Monitoring location on the Snake River at Keystone Science School, providing data on this important tributary.'
            },
            'Swan River Reach A- 1007': {
                'id': None,
                'site_number': 1007,
                'short_name': 'Swan River',
                'latitude': 39.6445,
                'longitude': -106.0789,
                'elevation': 9200,
                'description': 'Swan River monitoring site in Reach A, tracking water quality in this scenic mountain watershed.'
            }
        }
    
    # Display and edit existing sites
    st.subheader("Current Monitoring Sites")
    
    for i, (full_name, site_info) in enumerate(sites_data.items()):
        with st.expander(f"📍 {site_info['short_name']} - {full_name}", expanded=False):
            
            # Check if this site is being edited
            editing_key = f'editing_site_{i}'
            if st.session_state.get(editing_key, False):
                # Edit mode
                st.subheader("✏️ Edit Site Information")
                
                with st.form(f"edit_site_form_{i}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_site_number = st.number_input("Site Number", value=site_info['site_number'], step=1, key=f"site_num_{i}")
                        new_full_name = st.text_input("Full Site Name", value=full_name, key=f"full_name_{i}")
                        new_short_name = st.text_input("Short Name", value=site_info['short_name'], key=f"short_name_{i}")
                        new_elevation = st.number_input("Elevation (feet)", value=site_info['elevation'], step=1, key=f"elevation_{i}")
                    
                    with col2:
                        new_latitude = st.number_input("Latitude", value=site_info['latitude'], format="%.6f", key=f"lat_{i}")
                        new_longitude = st.number_input("Longitude", value=site_info['longitude'], format="%.6f", key=f"lon_{i}")
                    
                    new_description = st.text_area("Site Description", value=site_info['description'], height=100, key=f"desc_{i}")
                    
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.form_submit_button(" Save Changes", type="primary"):
                            try:
                                # Defer actual save; store pending site changes and confirm
                                st.session_state['pending_site_save'] = {
                                    'id': site_info.get('id'),
                                    'payload': {
                                        'site_number': new_site_number,
                                        'full_name': new_full_name,
                                        'short_name': new_short_name,
                                        'latitude': new_latitude,
                                        'longitude': new_longitude,
                                        'elevation': new_elevation,
                                        'description': new_description
                                    }
                                }
                                st.info("Please confirm your site changes below.")
                                
                            except Exception as e:
                                st.error(f" Error saving to database: {str(e)}")
                                st.info(" Changes saved temporarily in session")
                    
                    with col_cancel:
                        if st.form_submit_button(" Cancel"):
                            st.session_state[editing_key] = False
                            st.rerun()
            
            else:
                # Display mode
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"**Site Number:** {site_info['site_number']}")
                    st.write(f"**Full Name:** {full_name}")
                    st.write(f"**Short Name:** {site_info['short_name']}")
                    st.write(f"**Coordinates:** {site_info['latitude']:.4f}°N, {abs(site_info['longitude']):.4f}°W")
                
                with col2:
                    st.write(f"**Elevation:** {site_info['elevation']} feet")
                    st.write(f"**Description:** {site_info['description']}")
                
                with col3:
                    if st.button("✏️ Edit", key=f"edit_btn_{i}"):
                        st.session_state[editing_key] = True
                        st.rerun()
                
                # Mini map for each site
                site_map_data = pd.DataFrame({
                    'lat': [site_info['latitude']],
                    'lon': [site_info['longitude']]
                })
                st.map(site_map_data, zoom=13)

    # Confirmation UI for site changes
    if st.session_state.get('pending_site_save'):
        pending_site = st.session_state['pending_site_save']
        st.warning("Confirm updating site information:")
        payload = pending_site['payload']
        st.write(f"Short Name: {payload['short_name']}")
        st.write(f"Full Name: {payload['full_name']}")
        st.write(f"Site Number: {payload['site_number']}")
        st.write(f"Elevation: {payload['elevation']}")
        st.write(f"Lat/Lon: {payload['latitude']}, {payload['longitude']}")
        if payload.get('description'):
            st.write(f"Description: {payload['description']}")
        col_ok, col_cancel = st.columns(2)
        with col_ok:
            if st.button("✅ Confirm Site Update", type="primary"):
                try:
                    site_id = pending_site.get('id')
                    if site_id:
                        supabase.table('sites').update(payload).eq('id', site_id).execute()
                        st.success("Site updated successfully.")
                    else:
                        st.warning("Site ID not found - unable to write to database.")
                except Exception as e:
                    st.error(f"Error updating site: {str(e)}")
                finally:
                    st.session_state.pop('pending_site_save', None)
                    st.rerun()
        with col_cancel:
            if st.button("❌ Cancel Site Update"):
                st.session_state.pop('pending_site_save', None)
                st.info("Site changes canceled.")
    
    # Add new site section
    st.markdown("---")
    st.subheader("➕ Add New Monitoring Site")
    
    with st.form("add_new_site"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_site_number = st.number_input("Site Number", value=1000, step=1)
            new_full_name = st.text_input("Full Site Name")
            new_short_name = st.text_input("Short Name (for graphs)")
            new_elevation = st.number_input("Elevation (feet)", value=9000, step=1)
        
        with col2:
            new_latitude = st.number_input("Latitude", value=39.6000, format="%.6f")
            new_longitude = st.number_input("Longitude", value=-106.0000, format="%.6f")
        
        new_description = st.text_area("Site Description", placeholder="Describe the monitoring location, access points, and any relevant details...")
        
        if st.form_submit_button("🎯 Add New Site", type="primary"):
            if new_full_name and new_short_name and new_description:
                try:
                    # Add to database
                    supabase.table('sites').insert({
                        'site_number': new_site_number,
                        'full_name': new_full_name,
                        'short_name': new_short_name,
                        'latitude': new_latitude,
                        'longitude': new_longitude,
                        'elevation': new_elevation,
                        'description': new_description
                    }).execute()
                    
                    st.success(f"✅ Added new monitoring site: {new_short_name} to database!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Error adding site: {str(e)}")
            else:
                st.error("Please fill in both fields")
        

    # Removed database integration note per request

def login():
    """Handle user login"""
    st.title("🔐 Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        try:
            user = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state['user'] = user
            st.rerun()
        except Exception as e:
            st.error("Login failed. Please check your credentials.")
    
    if st.button("Create Account"):
        st.session_state['show_signup'] = True
        st.rerun()

def signup():
    """Handle user signup"""
    st.title("Create Account")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")
    
    if st.button("Sign Up"):
        if password != confirm_password:
            st.error("Passwords don't match!")
            return
        try:
            user = supabase.auth.sign_up({"email": email, "password": password})
            st.success("Account created successfully! Please login.")
            st.session_state['show_signup'] = False
            st.rerun()
        except Exception as e:
            st.error(f"Error creating account: {str(e)}")
    
    if st.button("Back to Login"):
        st.session_state['show_signup'] = False
        st.rerun()

def view_data():
    """Public data view for volunteers"""
    st.header("Water Quality Metrics Over Time")
    st.markdown("*Data collected by Citizen Scientists using CPW River Watch protocols*")
    
    # Check if user is admin for click functionality
    is_user_admin = False
    if 'user' in st.session_state:
        user_email = st.session_state['user'].user.email
        is_user_admin = is_admin(user_email)
    
    # Fetch and display data
    try:
        response = supabase.table('water_quality').select("*").order('date').execute()
        df = pd.DataFrame(response.data)
        
        if not df.empty:
            # Convert date column to datetime
            df['date'] = pd.to_datetime(df['date'])
            
            # Create abbreviated site names for legend using dynamic sites
            sites = get_sites()
            site_mapping = {full_name: short_name for full_name, short_name in sites}
            # Add backward compatibility for old site names
            site_mapping.update({
                'Site 1': 'Blue River',
                'Site 2': 'Snake River', 
                'Site 3': 'Swan River'
            })
            df['site_abbrev'] = df['site'].map(site_mapping)
            # Fallback: if a site value isn't in mapping, use the original site string
            df['site_abbrev'] = df['site_abbrev'].fillna(df['site'].astype(str))
            
            # Define the parameters to plot
            parameters = [
                ('dissolved_oxygen_mg', 'Dissolved Oxygen (mg/L)'),
                ('dissolved_oxygen_sat', 'Dissolved Oxygen (% saturation)'),
                ('hardness', 'Hardness (mg/L CaCO3)'),
                ('alkalinity', 'Alkalinity (mg/L CaCO3)'),
                ('ph', 'pH (S.U.s)'),
                ('temperature', 'Temperature (°C)'),
                ('flow', 'Flow (cfs)')
            ]
            
            # Create individual graphs for each parameter
            for param_col, param_title in parameters:
                if param_col in df.columns:
                    # Show admin instruction above each graph
                    if is_user_admin:
                        st.write("🎯 Click any data point below to select it for editing")
                    
                    # Filter out null values for proper line breaks
                    df_processed = df.copy()
                    # Ensure numeric dtype for column (coerce bad values to NaN)
                    df_processed[param_col] = pd.to_numeric(df_processed[param_col], errors='coerce')
                    
                    # Only convert zeros to NaN for parameters where zero is not meaningful
                    zero_not_meaningful = param_col in ['dissolved_oxygen_mg', 'dissolved_oxygen_sat', 'hardness', 'alkalinity', 'ph']
                    if zero_not_meaningful:
                        for site in df['site'].unique():
                            site_mask = df_processed['site'] == site
                            site_data = df_processed[site_mask].copy()
                            
                            # Convert zeros to NaN for this site's data to create breaks
                            site_data.loc[site_data[param_col] == 0, param_col] = float('nan')
                            
                            # Update the main dataframe
                            df_processed.loc[site_mask, param_col] = site_data[param_col]
                    
                    # After cleanup, aggregate to one row per site/date to avoid duplicates
                    df_param = df_processed[[
                        'date', 'site', 'site_abbrev', param_col, 'id'
                    ]].copy()
                    df_param = df_param.sort_values('date')
                    df_param = (
                        df_param
                        .groupby(['site', 'site_abbrev', 'date'], as_index=False)
                        .agg({param_col: 'first', 'id': 'first'})
                    )

                    # Define consistent colors for all sites
                    color_map = {
                        'Blue River': '#636EFA',  # Plotly default blue
                        'Snake River': '#EF553B', # Plotly default red  
                        'Swan River': '#00CC96'   # Plotly default green
                    }
                    
                    # Create the plot with custom_data for click handling
                    fig = px.line(
                        df_param, 
                        x='date', 
                        y=param_col, 
                        color='site_abbrev',
                        title=f'{param_title} - All Sites',
                        labels={'date': 'Date', param_col: param_title, 'site_abbrev': 'Site'},
                        custom_data=['site', 'id', 'date'],
                        markers=True,
                        color_discrete_map=color_map,
                        category_orders={'site_abbrev': ['Blue River', 'Snake River', 'Swan River']}
                    )
                    
                    fig.update_layout(
                        height=400,
                        xaxis=dict(tickformat='%m/%d/%Y'),
                        hoverlabel=dict(
                            bgcolor="white",
                            bordercolor="black",
                            font_size=12,
                            font_family="Arial"
                        )
                    )
                    
                    # Update hover template
                    fig.update_traces(
                        connectgaps=False,
                        hovertemplate="<b>%{fullData.name}</b><br>" +
                                    "Date: %{x|%m/%d/%Y}<br>" +
                                    f"{param_title}: %{{y}}<br>" +
                                    "<extra></extra>"
                    )
                    
                    # Show interactive charts for admin users, regular charts for volunteers
                    if is_user_admin:
                        # Use a simpler key that doesn't change
                        clicked_points = plotly_events(
                            fig,
                            click_event=True,
                            hover_event=False,
                            select_event=False,
                            key=f"plotly_{param_col}"
                        )
                        
                        # Handle click events
                        if clicked_points and len(clicked_points) > 0:
                            point = clicked_points[0]
                            point_index = point.get('pointIndex')
                            curve_number = point.get('curveNumber', 0)
                            
                            # Get the actual data point from the processed dataframe
                            # Filter by site first (curve_number corresponds to site)
                            unique_sites = df_processed['site_abbrev'].unique()
                            if curve_number < len(unique_sites):
                                clicked_site_abbrev = unique_sites[curve_number]
                                
                                # Get data for this site
                                site_data = df_processed[df_processed['site_abbrev'] == clicked_site_abbrev].reset_index(drop=True)
                                
                                if point_index < len(site_data):
                                    clicked_row = site_data.iloc[point_index]
                                    
                                    # Store the clicked data point info
                                    st.session_state['clicked_site'] = clicked_row['site']
                                    st.session_state['clicked_date'] = clicked_row['date'].strftime('%m/%d/%Y')
                                    st.session_state['clicked_id'] = clicked_row['id']
                                    
                                    # Show selection confirmation
                                    site_name = site_mapping.get(clicked_row['site'], clicked_row['site'])
                                    st.success(f"✅ Selected: {site_name} - {clicked_row['date'].strftime('%m/%d/%Y')} | Go to 'Add or Edit Data' tab to edit")
                    else:
                        # Show regular non-interactive chart for volunteers
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Add separation line after each graph
                    st.markdown("---")
        else:
            st.info("No water quality data available.")
            
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        st.exception(e)  # Show full error for debugging

def dashboard():
    """Main dashboard view for authenticated users"""
    # Create header bar with logo and title
    col1, col2 = st.columns([1, 4])
    with col1:
        # Add BRWG logo
        st.image("brwg logo.png", width=200)
    with col2:
        st.title("Water Quality Monitoring Dashboard")
    
    # Check if user is admin
    user_email = st.session_state['user'].user.email
    is_user_admin = is_admin(user_email)
    
    # Debug: Show current user email (remove this after testing)
    st.sidebar.write(f"Logged in as: {user_email}")
    st.sidebar.write(f"Admin status: {is_user_admin}")
    
    # Navigation - add admin tabs if user is admin
    if is_user_admin:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 View Data", "➕ Add or Edit Data", "📋 Data Entries", "🔧 Manage Sites", "👤 Add New Admin"])
    else:
        tab1, tab2 = st.tabs(["📊 View Data", "➕ Add or Edit Data"])
    
    # Handle tab switching from button clicks
    if st.session_state.get('switch_to_tab2', False):
        st.session_state['switch_to_tab2'] = False
        st.info("🎯 **Click the 'Add or Edit Data' tab above to edit your selected entry.**")
    
    # Handle automatic tab switching from graph clicks - moved to tab2 content
    
    with tab1:
        # Track tab switch
        if st.session_state.get('current_tab') != 'tab1':
            st.session_state['current_tab'] = 'tab1'
        view_data()
    
    with tab2:
        st.header("Add or Edit Water Quality Data")
        
        # Show success message if it exists
        if st.session_state.get('data_submitted', False):
            st.success(st.session_state.get('success_message', ''))
            st.balloons()
            st.session_state['data_submitted'] = False
            if 'success_message' in st.session_state:
                del st.session_state['success_message']
        
        # Initialize variables
        existing_data = None
        existing_id = None
        
        # Get current selections
        temp_sites = get_sites()
        temp_site_options = [full_name for full_name, short_name in temp_sites]
        
        # Handle navigation from clicked graph data point
        default_site_index = 0
        default_date = datetime.today().date()
        
        # Check if we have a clicked data point
        if st.session_state.get('clicked_id'):
            st.info("📍 Data point selected from graph - loading for editing...")
            
            # Fetch the specific record by ID
            try:
                response = supabase.table('water_quality').select("*").eq('id', st.session_state['clicked_id']).execute()
                if response.data and len(response.data) > 0:
                    existing_data = response.data[0]
                    existing_id = existing_data['id']
                    
                    # Map site name
                    site_name_mapping = {
                        'Site 1': 'Blue River at Silverthorne Pavilion- 196',
                        'Site 2': 'Snake River KSS- 52',
                        'Site 3': 'Swan River Reach A- 1007'
                    }
                    full_site_name = site_name_mapping.get(existing_data['site'], existing_data['site'])
                    
                    # Find site index
                    for i, site_option in enumerate(temp_site_options):
                        if full_site_name == site_option:
                            default_site_index = i
                            break
                    
                    # Set default date
                    default_date = pd.to_datetime(existing_data['date']).date()
                    
                    st.success(f"✅ Editing: {site_name_mapping.get(existing_data['site'], existing_data['site'])} - {default_date.strftime('%m/%d/%Y')}")
            except Exception as e:
                st.error(f"Error loading selected data: {str(e)}")
            
            # Clear the clicked session state after loading
            if 'clicked_id' in st.session_state:
                del st.session_state['clicked_id']
            if 'clicked_site' in st.session_state:
                del st.session_state['clicked_site']
            if 'clicked_date' in st.session_state:
                del st.session_state['clicked_date']
        
        # Site and date selection
        col1, col2 = st.columns(2)
        with col1:
            selected_site = st.selectbox("Site", temp_site_options, index=default_site_index, key="site_selection")
        with col2:
            selected_date = st.date_input("Date", value=default_date, format="MM/DD/YYYY", key="date_input")
        
        # If we don't have existing_data yet, try to fetch based on site and date
        if not existing_data and selected_site and selected_date:
            try:
                site_name_mapping = {
                    'Blue River at Silverthorne Pavilion- 196': 'Site 1',
                    'Snake River KSS- 52': 'Site 2',
                    'Swan River Reach A- 1007': 'Site 3'
                }
                db_site_name = site_name_mapping.get(selected_site, selected_site)
                
                response = supabase.table('water_quality').select("*").eq('site', db_site_name).eq('date', selected_date.strftime('%Y-%m-%d')).execute()
                if response.data and len(response.data) > 0:
                    existing_data = response.data[0]
                    existing_id = existing_data['id']
                    st.info("📝 Editing existing data entry")
                else:
                    st.info("➕ Creating new data entry")
            except Exception as e:
                st.error(f"Error checking for existing data: {str(e)}")
        
        # Data entry form
        with st.form("water_quality_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Dissolved Oxygen (mg/L)
                existing_do_mg = existing_data.get('dissolved_oxygen_mg') if existing_data else None
                col_input, col_checkbox = st.columns([3, 1])
                with col_input:
                    dissolved_oxygen_mg = st.number_input(
                        "Dissolved Oxygen (mg/L)", 
                        value=float(existing_do_mg) if existing_do_mg is not None else 0.0, 
                        format="%.2f"
                    )
                with col_checkbox:
                    st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                    do_mg_not_available = st.checkbox(
                        "N/A", 
                        value=existing_do_mg is None if existing_data else False,
                        key="do_mg_na",
                        help="Check if no measurement was taken"
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
                
                if do_mg_not_available:
                    dissolved_oxygen_mg = None
                
                # Dissolved Oxygen (% saturation)
                existing_do_sat = existing_data.get('dissolved_oxygen_sat') if existing_data else None
                col_input, col_checkbox = st.columns([3, 1])
                with col_input:
                    dissolved_oxygen_sat = st.number_input(
                        "Dissolved Oxygen (% saturation)", 
                        min_value=0.0, 
                        max_value=200.0,
                        value=float(existing_do_sat) if existing_do_sat is not None else 0.0, 
                        format="%.1f"
                    )
                with col_checkbox:
                    st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                    do_sat_not_available = st.checkbox(
                        "N/A", 
                        value=existing_do_sat is None if existing_data else False,
                        key="do_sat_na",
                        help="Check if no measurement was taken"
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
                
                if do_sat_not_available:
                    dissolved_oxygen_sat = None
                
                # Hardness
                existing_hardness = existing_data.get('hardness') if existing_data else None
                col_input, col_checkbox = st.columns([3, 1])
                with col_checkbox:
                    st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                    hardness_not_available = st.checkbox(
                        "N/A", 
                        value=existing_hardness is None if existing_data else False,
                        key="hardness_na",
                        help="Check if no measurement was taken"
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col_input:
                    if hardness_not_available:
                        st.text_input("Hardness (mg/L CaCO3)", value="Data not available", disabled=True)
                        hardness = None
                    else:
                        hardness = st.number_input(
                            "Hardness (mg/L CaCO3)", 
                            value=float(existing_hardness) if existing_hardness is not None else 0.0, 
                            format="%.1f"
                        )
                
                # Alkalinity
                existing_alkalinity = existing_data.get('alkalinity') if existing_data else None
                col_input, col_checkbox = st.columns([3, 1])
                with col_input:
                    alkalinity = st.number_input(
                        "Alkalinity (mg/L CaCO3)", 
                        value=float(existing_alkalinity) if existing_alkalinity is not None else 0.0, 
                        format="%.1f"
                    )
                with col_checkbox:
                    st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                    alkalinity_not_available = st.checkbox(
                        "N/A", 
                        value=existing_alkalinity is None if existing_data else False,
                        key="alkalinity_na",
                        help="Check if no measurement was taken"
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
                
                if alkalinity_not_available:
                    alkalinity = None
            
            with col2:
                # pH
                existing_ph = existing_data.get('ph') if existing_data else None
                col_input, col_checkbox = st.columns([3, 1])
                with col_input:
                    ph = st.number_input(
                        "pH (S.U.s)", 
                        min_value=0.0, 
                        max_value=14.0,
                        value=float(existing_ph) if existing_ph is not None else 7.0, 
                        format="%.1f"
                    )
                with col_checkbox:
                    st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                    ph_not_available = st.checkbox(
                        "N/A", 
                        value=existing_ph is None if existing_data else False,
                        key="ph_na",
                        help="Check if no measurement was taken"
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
                
                if ph_not_available:
                    ph = None
                
                # Temperature
                existing_temp = existing_data.get('temperature') if existing_data else None
                col_input, col_checkbox = st.columns([3, 1])
                with col_checkbox:
                    st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                    temp_not_available = st.checkbox(
                        "N/A", 
                        value=existing_temp is None if existing_data else False,
                        key="temp_na",
                        help="Check if no measurement was taken"
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
                
                with col_input:
                    if temp_not_available:
                        st.text_input("Temperature (°C)", value="Data not available", disabled=True)
                        temp = None
                    else:
                        temp = st.number_input(
                            "Temperature (°C)", 
                            value=float(existing_temp) if existing_temp is not None else 0.0, 
                            format="%.1f"
                        )
                
                # Flow
                existing_flow = existing_data.get('flow') if existing_data else None
                col_input, col_checkbox = st.columns([3, 1])
                with col_input:
                    flow = st.number_input(
                        "Flow (cfs)", 
                        value=float(existing_flow) if existing_flow is not None else 0.0, 
                        format="%.2f"
                    )
                with col_checkbox:
                    st.markdown('<div style="margin-top: 25px; font-size: 0.8em;">', unsafe_allow_html=True)
                    flow_not_available = st.checkbox(
                        "N/A", 
                        value=existing_flow is None if existing_data else False,
                        key="flow_na",
                        help="Check if no measurement was taken"
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
                
                if flow_not_available:
                    flow = None
                
                # Notes
                notes = st.text_area(
                    "Notes", 
                    value=existing_data.get('notes', '') if existing_data else ""
                )
            
            # Submit button
            button_text = "Update Data" if existing_data else "Submit Data"
            
            if st.form_submit_button(button_text):
                if not selected_date:
                    st.error("Please select a date before submitting.")
                else:
                    # Build payload
                    site_name_mapping = {
                        'Blue River at Silverthorne Pavilion- 196': 'Site 1',
                        'Snake River KSS- 52': 'Site 2',
                        'Swan River Reach A- 1007': 'Site 3'
                    }
                    db_site_name = site_name_mapping.get(selected_site, selected_site)
                    
                    data = {
                        'site': db_site_name,
                        'date': selected_date.strftime('%Y-%m-%d'),
                        'user_id': st.session_state['user'].user.id,
                        'notes': notes if notes else None
                    }
                    
                    # Add measurements (only if not N/A)
                    if dissolved_oxygen_mg is not None:
                        data['dissolved_oxygen_mg'] = dissolved_oxygen_mg
                    else:
                        data['dissolved_oxygen_mg'] = None
                        
                    if dissolved_oxygen_sat is not None:
                        data['dissolved_oxygen_sat'] = dissolved_oxygen_sat
                    else:
                        data['dissolved_oxygen_sat'] = None
                        
                    if hardness is not None:
                        data['hardness'] = hardness
                    else:
                        data['hardness'] = None
                        
                    if alkalinity is not None:
                        data['alkalinity'] = alkalinity
                    else:
                        data['alkalinity'] = None
                        
                    if ph is not None:
                        data['ph'] = ph
                    else:
                        data['ph'] = None
                        
                    if temp is not None:
                        data['temperature'] = temp
                    else:
                        data['temperature'] = None
                        
                    if flow is not None:
                        data['flow'] = flow
                    else:
                        data['flow'] = None
                    
                    # Store for confirmation
                    st.session_state['pending_wq_save'] = {
                        'data': data,
                        'existing_id': existing_id,
                        'selected_site': selected_site,
                        'selected_date': selected_date.strftime('%m/%d/%Y')
                    }
                    st.rerun()
        
        # Confirmation UI
        if st.session_state.get('pending_wq_save'):
            pending = st.session_state['pending_wq_save']
            st.warning("⚠️ Confirm saving the following changes:")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.write(f"**Site:** {pending['selected_site']}")
                st.write(f"**Date:** {pending['selected_date']}")
            with col_b:
                st.write("**Values:**")
                for k, v in pending['data'].items():
                    if k in ['site', 'date', 'user_id']:
                        continue
                    if k == 'notes' and v:
                        st.write(f"- Notes: {v}")
                    elif v is not None:
                        st.write(f"- {k}: {v}")
            
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("✅ Confirm Save", type="primary"):
                    try:
                        data = pending['data']
                        existing_id_local = pending['existing_id']
                        
                        if existing_id_local:
                            # Update existing record
                            supabase.table('water_quality').update(data).eq('id', existing_id_local).execute()
                            success_message = "✅ Data updated successfully!"
                        else:
                            # Insert new record
                            supabase.table('water_quality').insert(data).execute()
                            success_message = "✅ Data saved successfully!"
                        
                        # Clear caches
                        if hasattr(st, 'cache_data'):
                            st.cache_data.clear()
                        if hasattr(st, 'cache_resource'):
                            st.cache_resource.clear()
                        
                        # Set success message and clear pending save
                        st.session_state['success_message'] = success_message
                        st.session_state['data_submitted'] = True
                        st.session_state.pop('pending_wq_save', None)
                        
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Error submitting data: {str(e)}")
                        st.exception(e)
            
            with col_cancel:
                if st.button("❌ Cancel"):
                    st.session_state.pop('pending_wq_save', None)
                    st.rerun()

    # Admin tab for data editing
    if is_user_admin:
        with tab3:
            # Track tab switch
            if st.session_state.get('current_tab') != 'tab3':
                st.session_state['current_tab'] = 'tab3'
            edit_data()
    
    # Admin tab for site management
    if is_user_admin:
        with tab4:
            # Track tab switch
            if st.session_state.get('current_tab') != 'tab4':
                st.session_state['current_tab'] = 'tab4'
            manage_sites(is_user_admin)
        
        # Add New Admin tab
        with tab5:
            st.header("👤 Add New Admin")
            
            st.subheader("Create New Admin Account")
            with st.form("add_admin_form"):
                admin_email = st.text_input("Admin Email Address")
                admin_password = st.text_input("Temporary Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                
                st.info("💡 The new admin will be able to log in immediately with these credentials.")
                
                if st.form_submit_button("Create Admin Account"):
                    if not admin_email or not admin_password:
                        st.error("Please fill in all fields")
                    elif admin_password != confirm_password:
                        st.error("Passwords don't match!")
                    else:
                        try:
                            # Create account in Supabase Auth
                            user = supabase.auth.sign_up({
                                "email": admin_email,
                                "password": admin_password
                            })
                            
                            # Add to approved admins list (if using pending_admins table)
                            try:
                                pending_data = {
                                    'email': admin_email,
                                    'status': 'approved',
                                    'approved_by': user_email,
                                    'approved_at': 'now()'
                                }
                                supabase.table('pending_admins').insert(pending_data).execute()
                            except:
                                pass  # Table might not exist
                            
                            st.success(f"✅ Admin account created successfully for {admin_email}")
                            st.info("They can now log in with the provided credentials.")
                            
                        except Exception as e:
                            if "User already registered" in str(e):
                                # User exists, check if already admin or add them
                                try:
                                    # First check if they're already in the admin list
                                    existing_admin = supabase.table('pending_admins').select("*").eq('email', admin_email).execute()
                                    
                                    if existing_admin.data:
                                        # Update existing record to approved status
                                        supabase.table('pending_admins').update({
                                            'status': 'approved',
                                            'approved_by': user_email,
                                            'approved_at': 'now()'
                                        }).eq('email', admin_email).execute()
                                        st.success(f"✅ {admin_email} admin status updated successfully!")
                                    else:
                                        # Insert new admin record
                                        pending_data = {
                                            'email': admin_email,
                                            'status': 'approved',
                                            'approved_by': user_email,
                                            'approved_at': 'now()'
                                        }
                                        supabase.table('pending_admins').insert(pending_data).execute()
                                        st.success(f"✅ {admin_email} added to admin list successfully!")
                                    
                                    st.info("They can now log in with their existing credentials.")
                                except Exception as db_error:
                                    st.error(f"User exists but couldn't add to admin list: {str(db_error)}")
                            else:
                                st.error(f"Error creating admin account: {str(e)}")
            
            st.markdown("---")
            
            st.subheader("Current Admins")
            st.write("**Hardcoded Admins:**")
            st.write("• megandaiger@gmail.com")
            
            # Show approved admins from database
            try:
                approved_response = supabase.table('pending_admins').select("*").eq('status', 'approved').execute()
                if approved_response.data:
                    st.write("**Database Approved Admins:**")
                    for admin in approved_response.data:
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.write(f"• {admin['email']}")
                        with col2:
                            if st.button("🗑️", key=f"remove_admin_{admin['id']}", help="Remove admin access"):
                                supabase.table('pending_admins').update({'status': 'denied'}).eq('id', admin['id']).execute()
                                st.success(f"Removed admin access for {admin['email']}")
                                st.rerun()
            except:
                st.info("No additional admins found in database.")
    
    # Logout button
    if st.sidebar.button("Logout"):
        if 'user' in st.session_state:
            del st.session_state['user']
        st.rerun()

# Main app logic
if 'user' not in st.session_state:
    # Create header bar with logo and buttons
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        # Add BRWG logo
        st.image("brwg logo.png", width=200)
    with col2:
        st.title("Water Quality Monitoring Dashboard")
    with col3:
        # Initialize session state variables
        if 'show_login' not in st.session_state:
            st.session_state['show_login'] = False
        if 'show_site_info' not in st.session_state:
            st.session_state['show_site_info'] = False
        
        # Buttons in top right - closer together
        if st.button("📍 Site Info", key="header_site_info_btn"):
            st.session_state['show_site_info'] = not st.session_state['show_site_info']
            st.session_state['show_login'] = False  # Close login if open
        if st.button("🔐 Staff Login", key="header_login_btn"):
            st.session_state['show_login'] = not st.session_state['show_login']
            st.session_state['show_site_info'] = False  # Close site info if open
    
    # Show login form if button was clicked
    if st.session_state.get('show_login', False):
        with st.container():
            st.markdown("---")
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.subheader("Login")
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                
                if st.button("Login"):
                    try:
                        user = supabase.auth.sign_in_with_password({"email": email, "password": password})
                        st.session_state['user'] = user
                        st.rerun()
                    except Exception as e:
                        st.error("Login failed. Please check your credentials.")
                
                st.info("💡 Need admin access? Contact the administrator to have an account created for you.")
                
                st.info("💡 You can view all water quality data without logging in!")
            st.markdown("---")
    
    # Show site information if button was clicked
    if st.session_state.get('show_site_info', False):
        with st.container():
            st.markdown("---")
            site_information()
            st.markdown("---")
    
    # Show public data view
    view_data()
else:
    dashboard()
