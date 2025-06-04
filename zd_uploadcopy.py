import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import html2text
import time
import json
import re
import random
import string
import datetime
import pandas as pd
import os
import urllib.parse

# Constants
RATE_LIMIT_DELAY = 0.1
DEFAULT_LANGUAGE = "en"
CONFIG_FILE = "zendesk_ada_configs.json"

# Configuration Management Functions
def save_configuration(config_name, config_data):
    """Save configuration to file."""
    try:
        configs = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                configs = json.load(f)
        
        configs[config_name] = config_data
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(configs, f, indent=2)
        
        if 'saved_configs' not in st.session_state:
            st.session_state['saved_configs'] = {}
        st.session_state['saved_configs'][config_name] = config_data
        
        return True
    except Exception as e:
        st.error(f"Failed to save configuration: {str(e)}")
        return False

def load_configuration(config_name):
    """Load configuration from file."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                configs = json.load(f)
                return configs.get(config_name, {})
    except Exception as e:
        st.error(f"Failed to load configuration: {str(e)}")
    return {}

def get_saved_config_names():
    """Get list of saved configuration names from file."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                configs = json.load(f)
                return list(configs.keys())
    except Exception as e:
        st.error(f"Failed to read configurations: {str(e)}")
    return []

def delete_configuration(config_name):
    """Delete a saved configuration from file."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                configs = json.load(f)
            
            if config_name in configs:
                del configs[config_name]
                
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(configs, f, indent=2)
                
                if 'saved_configs' in st.session_state and config_name in st.session_state['saved_configs']:
                    del st.session_state['saved_configs'][config_name]
                
                return True
    except Exception as e:
        st.error(f"Failed to delete configuration: {str(e)}")
    return False

def load_all_configs_to_session():
    """Load all configurations from file to session state."""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                configs = json.load(f)
                st.session_state['saved_configs'] = configs
    except Exception as e:
        st.error(f"Failed to load configurations: {str(e)}")

# Logging System
def init_logs():
    """Initialize logs in session state."""
    if 'api_logs' not in st.session_state:
        st.session_state['api_logs'] = []

def add_log(action, status, endpoint="", request_payload=None, response_payload=None, details=""):
    """Add a detailed log entry."""
    if 'api_logs' not in st.session_state:
        st.session_state['api_logs'] = []
    
    request_str = ""
    response_str = ""
    
    if request_payload:
        try:
            request_str = json.dumps(request_payload, indent=2)[:500] + ("..." if len(json.dumps(request_payload)) > 500 else "")
        except:
            request_str = str(request_payload)[:500]
    
    if response_payload:
        try:
            response_str = json.dumps(response_payload, indent=2)[:500] + ("..." if len(json.dumps(response_payload)) > 500 else "")
        except:
            response_str = str(response_payload)[:500]
    
    log_entry = {
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        "action": action,
        "status": status,
        "endpoint": endpoint,
        "request": request_str,
        "response": response_str,
        "details": details
    }
    st.session_state['api_logs'].append(log_entry)

def clear_logs():
    """Clear all logs."""
    st.session_state['api_logs'] = []

# Utility Functions
def is_valid_subdomain(subdomain):
    """Check if the provided subdomain is valid."""
    regex = re.compile(r'^[a-zA-Z0-9-]+$')
    return re.match(regex, subdomain) is not None

def check_article_size(content):
    """Check if article content size is below 100KB."""
    max_size_kb = 100
    content_size_kb = len(content.encode('utf-8')) / 1024
    return content_size_kb <= max_size_kb

def get_zd_auth():
    """Get Zendesk authentication tuple."""
    zd_email = st.session_state.get('zd_email', '')
    zd_token = st.session_state.get('zd_token', '')
    if not zd_email or not zd_token:
        return None
    return HTTPBasicAuth(f"{zd_email}/token", zd_token)

def get_brand_base_url(brand):
    """Get the correct base URL for a brand's Help Center API."""
    if brand.get('host_mapping'):
        return f"https://{brand['host_mapping']}"
    else:
        return f"https://{brand['subdomain']}.zendesk.com"

# API Functions
def get_locales():
    """Fetch available locales from Zendesk."""
    zd_subdomain = st.session_state.get('zd_subdomain', '')
    include_restricted = st.session_state.get('include_restricted', True)
    
    endpoint = f"https://{zd_subdomain}.zendesk.com/api/v2/locales"
    add_log("Fetch Locales", "INFO", endpoint, details="Requesting locales from Zendesk")
    
    auth = get_zd_auth() if include_restricted else None
    response = requests.get(endpoint, auth=auth)
    
    if response.status_code == 200:
        response_data = response.json()
        locales = [locale['locale'].lower() for locale in response_data.get('locales', [])]
        result = locales if locales else [DEFAULT_LANGUAGE]
        add_log("Fetch Locales", "SUCCESS", endpoint, None, response_data, f"Found {len(result)} locales")
        return result
    else:
        error_response = {"status_code": response.status_code, "error": response.text}
        add_log("Fetch Locales", "ERROR", endpoint, None, error_response, f"Status: {response.status_code}")
        st.error(f"Failed to fetch locales: {response.text}")
        return [DEFAULT_LANGUAGE]

def get_categories():
    """Fetch available categories from Zendesk."""
    zd_subdomain = st.session_state.get('zd_subdomain', '')
    include_restricted = st.session_state.get('include_restricted', True)
    
    endpoint = f"https://{zd_subdomain}.zendesk.com/api/v2/help_center/categories"
    add_log("Fetch Categories", "INFO", endpoint, details="Requesting categories from Zendesk")
    
    auth = get_zd_auth() if include_restricted else None
    response = requests.get(endpoint, auth=auth)
    
    if response.status_code == 200:
        response_data = response.json()
        categories = response_data.get('categories', [])
        add_log("Fetch Categories", "SUCCESS", endpoint, None, response_data, f"Found {len(categories)} categories")
        return categories
    else:
        error_response = {"status_code": response.status_code, "error": response.text}
        add_log("Fetch Categories", "ERROR", endpoint, None, error_response, f"Status: {response.status_code}")
        st.error(f"Failed to fetch categories: {response.text}")
        return []

def get_brands():
    """Fetch available brands from Zendesk."""
    zd_subdomain = st.session_state.get('zd_subdomain', '')
    include_restricted = st.session_state.get('include_restricted', True)
    
    endpoint = f"https://{zd_subdomain}.zendesk.com/api/v2/brands"
    add_log("Fetch Brands", "INFO", endpoint, details="Requesting brands from Zendesk")
    
    auth = get_zd_auth() if include_restricted else None
    response = requests.get(endpoint, auth=auth)
    
    if response.status_code == 200:
        response_data = response.json()
        brands = response_data.get('brands', [])
        add_log("Fetch Brands", "SUCCESS", endpoint, None, response_data, f"Found {len(brands)} brands")
        return brands
    else:
        error_response = {"status_code": response.status_code, "error": response.text}
        add_log("Fetch Brands", "ERROR", endpoint, None, error_response, f"Status: {response.status_code}")
        st.error(f"Failed to fetch brands: {response.text}")
        return []

def get_sections():
    """Fetch available sections from Zendesk."""
    zd_subdomain = st.session_state.get('zd_subdomain', '')
    include_restricted = st.session_state.get('include_restricted', True)
    
    endpoint = f"https://{zd_subdomain}.zendesk.com/api/v2/help_center/sections"
    add_log("Fetch Sections", "INFO", endpoint, details="Requesting sections from Zendesk")
    
    auth = get_zd_auth() if include_restricted else None
    response = requests.get(endpoint, auth=auth)
    
    if response.status_code == 200:
        response_data = response.json()
        sections = response_data.get('sections', [])
        add_log("Fetch Sections", "SUCCESS", endpoint, None, response_data, f"Found {len(sections)} sections")
        return sections
    else:
        error_response = {"status_code": response.status_code, "error": response.text}
        add_log("Fetch Sections", "ERROR", endpoint, None, error_response, f"Status: {response.status_code}")
        st.error(f"Failed to fetch sections: {response.text}")
        return []

def get_existing_knowledge_sources():
    """Fetch existing knowledge sources from Ada."""
    ada_subdomain = st.session_state.get('ada_subdomain', '')
    ada_api_token = st.session_state.get('ada_api_token', '')
    
    endpoint = f"https://{ada_subdomain}.ada.support/api/v2/knowledge/sources/"
    add_log("Fetch Knowledge Sources", "INFO", endpoint, details="Requesting knowledge sources from Ada")
    
    headers = {
        "Authorization": f"Bearer {ada_api_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        response_data = response.json()
        sources = response_data.get('data', [])
        add_log("Fetch Knowledge Sources", "SUCCESS", endpoint, None, response_data, f"Found {len(sources)} knowledge sources")
        return sources
    else:
        error_response = {"status_code": response.status_code, "error": response.text}
        add_log("Fetch Knowledge Sources", "ERROR", endpoint, None, error_response, f"Status: {response.status_code}")
        st.error(f"Failed to fetch knowledge sources. Status: {response.status_code}")
        return []

def generate_simple_id(length=15):
    """Generate a random alphanumeric ID of specified length."""
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def create_knowledge_source_with_random_id(name):
    """Create a new knowledge source with user-provided name and simple random ID."""
    ada_subdomain = st.session_state.get('ada_subdomain', '')
    ada_api_token = st.session_state.get('ada_api_token', '')
    
    knowledge_source_id = generate_simple_id(15)
    endpoint = f"https://{ada_subdomain}.ada.support/api/v2/knowledge/sources/"
    
    headers = {
        "Authorization": f"Bearer {ada_api_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "id": knowledge_source_id,
        "name": name
    }
    
    add_log("Create Knowledge Source", "INFO", endpoint, payload, details=f"Creating source: {name}")
    
    response = requests.post(endpoint, headers=headers, json=payload)
    
    if response.status_code in [200, 201]:
        response_data = response.json()
        add_log("Create Knowledge Source", "SUCCESS", endpoint, payload, response_data, f"Created: {name} (ID: {knowledge_source_id})")
        
        if 'data' in response_data and 'id' in response_data['data']:
            return response_data['data']['id']
        elif 'id' in response_data:
            return response_data['id']
        elif isinstance(response_data, dict) and 'data' in response_data:
            return response_data['data'].get('id', knowledge_source_id)
        else:
            add_log("Create Knowledge Source", "WARNING", endpoint, payload, response_data, "Unexpected response structure, using generated ID")
            return knowledge_source_id
    else:
        error_response = {"status_code": response.status_code, "error": response.text}
        add_log("Create Knowledge Source", "ERROR", endpoint, payload, error_response, f"Status: {response.status_code}")
        st.error(f"Failed to create knowledge source. Status: {response.status_code}, Response: {response.text}")
        return None

# Article Fetching Functions
def fetch_articles_with_filters(selected_locales=None, selected_brands=None, selected_categories=None):
    """Fetch articles with filters applied - only fetch what's specifically requested."""
    include_restricted = st.session_state.get('include_restricted', True)
    
    all_articles = []
    auth = get_zd_auth() if include_restricted else None
    
    filter_parts = []
    if selected_locales:
        filter_parts.append(f"locales: {selected_locales}")
    if selected_brands:
        filter_parts.append(f"brands: {selected_brands}")
    if selected_categories:
        filter_parts.append(f"categories: {selected_categories}")
    filter_desc = ", ".join(filter_parts) if filter_parts else "no filters - will not fetch anything"
    
    if not selected_locales and not selected_brands and not selected_categories:
        add_log("Fetch Articles", "INFO", "", {}, {}, "No filters specified - not fetching any articles")
        st.info("🔍 No filters selected. Please enable and select at least one filter (Locale, Brand, or Category) to fetch articles.")
        return []
    
    selected_brand_objects = []
    if selected_brands and 'brands' in st.session_state:
        selected_brand_objects = [brand for brand in st.session_state['brands'] if brand['id'] in selected_brands]
    
    if selected_brands and not selected_locales:
        for brand in selected_brand_objects:
            articles = fetch_brand_articles(brand, auth)
            all_articles.extend(articles)
            
    elif selected_locales and not selected_brands:
        zd_subdomain = st.session_state.get('zd_subdomain', '')
        for locale in selected_locales:
            articles = fetch_locale_articles(locale, auth, zd_subdomain)
            all_articles.extend(articles)
            
    elif selected_brands and selected_locales:
        for brand in selected_brand_objects:
            for locale in selected_locales:
                articles = fetch_brand_locale_articles(brand, locale, auth)
                all_articles.extend(articles)
                
    elif selected_categories and not selected_brands and not selected_locales:
        zd_subdomain = st.session_state.get('zd_subdomain', '')
        articles = fetch_all_articles_for_category_filter(auth, zd_subdomain)
        all_articles = filter_by_categories(articles, selected_categories)
    
    if selected_categories and (selected_brands or selected_locales):
        all_articles = filter_by_categories(all_articles, selected_categories)
    
    seen_ids = set()
    unique_articles = []
    for article in all_articles:
        article_id = article.get('id')
        if article_id not in seen_ids:
            seen_ids.add(article_id)
            unique_articles.append(article)
    
    add_log("Fetch Articles", "SUCCESS", "Multiple endpoints", 
           {"filters": filter_desc}, 
           {"total_articles": len(unique_articles)}, 
           f"Completed: {len(unique_articles)} articles fetched with filters: {filter_desc}")
    
    return unique_articles

def fetch_brand_articles(brand, auth):
    """Fetch articles for a specific brand using its own subdomain."""
    articles = []
    page = 1
    
    brand_base_url = get_brand_base_url(brand)
    base_url = f"{brand_base_url}/api/v2/help_center/articles"
    
    add_log("Fetch Brand Articles", "INFO", base_url, {"brand": brand['name']}, 
           details=f"Fetching from brand: {brand['name']} via {brand_base_url}")
    
    while True:
        params = {'page': page, 'per_page': 100}
        endpoint = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        response = requests.get(base_url, auth=auth, params=params)
        time.sleep(RATE_LIMIT_DELAY)
        
        if response.status_code == 200:
            data = response.json()
            page_articles = data.get('articles', [])
            
            for article in page_articles:
                article['_brand_name'] = brand['name']
                article['_brand_id'] = brand['id']
                article['_brand_subdomain'] = brand.get('subdomain', '')
                article['_brand_url'] = brand_base_url
            
            articles.extend(page_articles)
            
            add_log("Fetch Brand Articles", "SUCCESS", endpoint, params, 
                   {"articles_on_page": len(page_articles), "total_so_far": len(articles)},
                   f"Brand: {brand['name']}, Page: {page}")
            
            if data.get('next_page'):
                page += 1
            else:
                break
        else:
            error_response = {"status_code": response.status_code, "error": response.text}
            add_log("Fetch Brand Articles", "ERROR", endpoint, params, error_response,
                   f"Failed for brand: {brand['name']}")
            st.error(f"Failed to fetch articles for brand '{brand['name']}': {response.text}")
            break
    
    return articles

def fetch_locale_articles(locale, auth, zd_subdomain):
    """Fetch articles for a specific locale from main subdomain."""
    articles = []
    page = 1
    base_url = f"https://{zd_subdomain}.zendesk.com/api/v2/help_center/{locale}/articles"
    
    add_log("Fetch Locale Articles", "INFO", base_url, {"locale": locale},
           details=f"Fetching locale: {locale}")
    
    while True:
        params = {'page': page, 'per_page': 100}
        endpoint = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        response = requests.get(base_url, auth=auth, params=params)
        time.sleep(RATE_LIMIT_DELAY)
        
        if response.status_code == 200:
            data = response.json()
            page_articles = data.get('articles', [])
            articles.extend(page_articles)
            
            add_log("Fetch Locale Articles", "SUCCESS", endpoint, params,
                   {"articles_on_page": len(page_articles), "total_so_far": len(articles)},
                   f"Locale: {locale}, Page: {page}")
            
            if data.get('next_page'):
                page += 1
            else:
                break
        else:
            error_response = {"status_code": response.status_code, "error": response.text}
            add_log("Fetch Locale Articles", "ERROR", endpoint, params, error_response,
                   f"Failed for locale: {locale}")
            st.error(f"Failed to fetch articles for locale '{locale}': {response.text}")
            break
    
    return articles

def fetch_brand_locale_articles(brand, locale, auth):
    """Fetch articles for a specific brand and locale combination."""
    articles = []
    page = 1
    
    brand_base_url = get_brand_base_url(brand)
    base_url = f"{brand_base_url}/api/v2/help_center/{locale}/articles"
    
    add_log("Fetch Brand+Locale Articles", "INFO", base_url, 
           {"brand": brand['name'], "locale": locale},
           details=f"Fetching brand: {brand['name']}, locale: {locale}")
    
    while True:
        params = {'page': page, 'per_page': 100}
        endpoint = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        response = requests.get(base_url, auth=auth, params=params)
        time.sleep(RATE_LIMIT_DELAY)
        
        if response.status_code == 200:
            data = response.json()
            page_articles = data.get('articles', [])
            
            for article in page_articles:
                article['_brand_name'] = brand['name']
                article['_brand_id'] = brand['id']
                article['_brand_subdomain'] = brand.get('subdomain', '')
                article['_brand_url'] = brand_base_url
            
            articles.extend(page_articles)
            
            add_log("Fetch Brand+Locale Articles", "SUCCESS", endpoint, params,
                   {"articles_on_page": len(page_articles), "total_so_far": len(articles)},
                   f"Brand: {brand['name']}, Locale: {locale}, Page: {page}")
            
            if data.get('next_page'):
                page += 1
            else:
                break
        else:
            error_response = {"status_code": response.status_code, "error": response.text}
            add_log("Fetch Brand+Locale Articles", "ERROR", endpoint, params, error_response,
                   f"Failed for brand: {brand['name']}, locale: {locale}")
            st.error(f"Failed to fetch articles for brand '{brand['name']}', locale '{locale}': {response.text}")
            break
    
    return articles

def fetch_all_articles_for_category_filter(auth, zd_subdomain):
    """Fetch all articles when we need to filter by category."""
    articles = []
    page = 1
    base_url = f"https://{zd_subdomain}.zendesk.com/api/v2/help_center/articles"
    
    while True:
        params = {'page': page, 'per_page': 100}
        response = requests.get(base_url, auth=auth, params=params)
        time.sleep(RATE_LIMIT_DELAY)
        
        if response.status_code == 200:
            data = response.json()
            articles.extend(data.get('articles', []))
            if data.get('next_page'):
                page += 1
            else:
                break
        else:
            st.error(f"Failed to fetch articles for category filtering: {response.text}")
            break
    return articles

def filter_by_categories(articles, selected_categories):
    """Filter articles by category."""
    filtered_articles = []
    for article in articles:
        article_section_id = article.get('section_id')
        if article_section_id and 'sections' in st.session_state:
            for section in st.session_state['sections']:
                if section['id'] == article_section_id:
                    if section.get('category_id') in selected_categories:
                        filtered_articles.append(article)
                        break
    return filtered_articles

def format_articles_for_ada(articles, knowledge_source_id):
    """Format articles for Ada with proper field mapping and corrected URLs."""
    add_log("Format Articles", "INFO", details=f"Formatting {len(articles)} articles")
    
    formatted_articles = []
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    skipped_count = 0

    for article in articles:
        zd_id = article.get("id")
        zd_title = article.get("title", "")
        zd_body = article.get("body", "")
        zd_html_url = article.get("html_url", "")
        zd_locale = article.get("locale", "en")
        
        # Fix the URL to use the correct brand domain
        corrected_url = zd_html_url
        if article.get('_brand_url') and zd_html_url:
            parsed_url = urllib.parse.urlparse(zd_html_url)
            path = parsed_url.path
            query = parsed_url.query
            fragment = parsed_url.fragment
            
            brand_base_url = article.get('_brand_url')
            corrected_url = f"{brand_base_url}{path}"
            if query:
                corrected_url += f"?{query}"
            if fragment:
                corrected_url += f"#{fragment}"
            
            add_log("URL Correction", "INFO", details=f"Original: {zd_html_url} -> Corrected: {corrected_url}")
        
        if zd_body is None:
            zd_body = ""
        markdown_content = converter.handle(zd_body)
        
        if not check_article_size(markdown_content):
            skipped_count += 1
            add_log("Format Articles", "WARNING", details=f"Article '{zd_title[:30]}...' exceeds 100KB, skipped")
            continue

        ada_article = {
            "id": f"zd_{zd_id}",
            "name": zd_title[:255],
            "content": markdown_content,
            "knowledge_source_id": knowledge_source_id,
            "url": corrected_url,
            "tag_ids": [],
            "language": zd_locale.lower() if zd_locale else "en"
        }
        
        formatted_articles.append(ada_article)
    
    add_log("Format Articles", "SUCCESS", details=f"Formatted {len(formatted_articles)} articles, skipped {skipped_count}")
    return {"articles": formatted_articles}

def upload_articles_to_ada(formatted_articles):
    """Upload articles to Ada one by one using the bulk endpoint."""
    ada_subdomain = st.session_state.get('ada_subdomain', '')
    ada_api_token = st.session_state.get('ada_api_token', '')
    
    headers = {
        "Authorization": f"Bearer {ada_api_token}",
        "Content-Type": "application/json"
    }
    
    articles = formatted_articles["articles"]
    endpoint = f"https://{ada_subdomain}.ada.support/api/v2/knowledge/bulk/articles/"
    add_log("Upload Articles", "INFO", endpoint, details=f"Starting upload of {len(articles)} articles")
    
    success_count = 0
    error_count = 0
    
    for i, article in enumerate(articles, 1):
        payload = [article]
        
        while True:
            log_payload = [{**article, "content": article["content"][:100] + "..." if len(article["content"]) > 100 else article["content"]}]
            add_log("Upload Article", "INFO", endpoint, log_payload, details=f"Uploading article {i}/{len(articles)}: {article['name'][:40]}...")
            
            response = requests.post(endpoint, headers=headers, json=payload)
            time.sleep(RATE_LIMIT_DELAY)
            
            if response.status_code in [200, 201]:
                success_count += 1
                response_data = response.json()
                add_log("Upload Article", "SUCCESS", endpoint, log_payload, response_data, f"({i}/{len(articles)}) {article['name'][:40]}...")
                st.success(f"Successfully uploaded article {i}/{len(articles)}: '{article['name']}'")
                break
            elif response.status_code == 429:
                error_response = {"status_code": response.status_code, "error": "Rate limited"}
                add_log("Upload Article", "WARNING", endpoint, log_payload, error_response, f"Rate limited on article {i}")
                st.warning(f"Rate limited while uploading article {i}. Retrying after delay...")
                time.sleep(60)
            else:
                error_count += 1
                error_response = {"status_code": response.status_code, "error": response.text}
                add_log("Upload Article", "ERROR", endpoint, log_payload, error_response, f"({i}/{len(articles)}) {article['name'][:30]}...")
                st.error(f"Failed to upload article {i}: '{article['name']}'. Status: {response.status_code}")
                break
    
    summary = {"success_count": success_count, "error_count": error_count, "total_articles": len(articles)}
    add_log("Upload Articles", "SUCCESS", endpoint, None, summary, f"Upload completed: {success_count} success, {error_count} errors")

# UI CODE STARTS HERE
st.title("Zendesk Article Management")
st.write("This integration grabs articles from a Zendesk Help Center and pushes them to Ada API")

init_logs()
load_all_configs_to_session()

# Configuration Management Section
st.subheader("Configuration Management")
st.write("💾 Configurations are saved to file and persist between sessions")

col1, col2, col3 = st.columns(3)

with col1:
    config_name = st.text_input("Configuration Name", placeholder="e.g., Production Config", key="config_name_input")

with col2:
    if st.button("💾 Save Current Config", key="save_config_btn"):
        if config_name:
            config_data = {
                "zd_subdomain": st.session_state.get('zd_subdomain', ''),
                "zd_email": st.session_state.get('zd_email', ''),
                "zd_token": st.session_state.get('zd_token', ''),
                "ada_subdomain": st.session_state.get('ada_subdomain', ''),
                "ada_api_token": st.session_state.get('ada_api_token', ''),
                "include_restricted": st.session_state.get('include_restricted', True),
                "saved_at": datetime.datetime.now().isoformat()
            }
            if save_configuration(config_name, config_data):
                st.success(f"✅ Configuration '{config_name}' saved to file!")
            else:
                st.error("❌ Failed to save configuration")
        else:
            st.error("Please provide a configuration name")

with col3:
    saved_configs = get_saved_config_names()
    if saved_configs:
        selected_config = st.selectbox("📂 Load Saved Config", [""] + saved_configs, key="config_selector")
        if st.button("📥 Load Config", key="load_config_btn") and selected_config:
            config_data = load_configuration(selected_config)
            if config_data:
                st.session_state['zd_subdomain'] = config_data.get('zd_subdomain', '')
                st.session_state['zd_email'] = config_data.get('zd_email', '')
                st.session_state['zd_token'] = config_data.get('zd_token', '')
                st.session_state['ada_subdomain'] = config_data.get('ada_subdomain', '')
                st.session_state['ada_api_token'] = config_data.get('ada_api_token', '')
                st.session_state['include_restricted'] = config_data.get('include_restricted', True)
                st.success(f"✅ Configuration '{selected_config}' loaded!")
                st.rerun()
            else:
                st.error("❌ Failed to load configuration")

# Show config file location
if os.path.exists(CONFIG_FILE):
    file_path = os.path.abspath(CONFIG_FILE)
    st.info(f"📁 Configurations saved in: `{file_path}`")

# Manage saved configurations
if saved_configs:
    with st.expander("🗂️ Manage Saved Configurations"):
        st.write(f"**Found {len(saved_configs)} saved configuration(s):**")
        
        for config in saved_configs:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                config_data = load_configuration(config)
                saved_at = config_data.get('saved_at', 'Unknown')
                if saved_at != 'Unknown':
                    try:
                        saved_date = datetime.datetime.fromisoformat(saved_at).strftime('%Y-%m-%d %H:%M')
                    except:
                        saved_date = saved_at
                else:
                    saved_date = 'Unknown'
                
                st.write(f"**{config}**")
                st.write(f"🗓️ Saved: {saved_date}")
                st.write(f"🌐 ZD: {config_data.get('zd_subdomain', 'Not set')}")
                st.write(f"🤖 Ada: {config_data.get('ada_subdomain', 'Not set')}")
            
            with col2:
                if st.button(f"📥 Load", key=f"load_config_{config}"):
                    config_data = load_configuration(config)
                    if config_data:
                        st.session_state['zd_subdomain'] = config_data.get('zd_subdomain', '')
                        st.session_state['zd_email'] = config_data.get('zd_email', '')
                        st.session_state['zd_token'] = config_data.get('zd_token', '')
                        st.session_state['ada_subdomain'] = config_data.get('ada_subdomain', '')
                        st.session_state['ada_api_token'] = config_data.get('ada_api_token', '')
                        st.session_state['include_restricted'] = config_data.get('include_restricted', True)
                        st.success(f"Loaded '{config}'")
                        st.rerun()
            
            with col3:
                if st.button(f"🗑️ Delete", key=f"delete_config_{config}"):
                    if delete_configuration(config):
                        st.success(f"Deleted '{config}'")
                        st.rerun()
                    else:
                        st.error(f"Failed to delete '{config}'")
            
            st.divider()
        
        # Export/Import functionality
        st.subheader("📤📥 Export/Import Configurations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📤 Export All Configs", key="export_configs_btn"):
                try:
                    if os.path.exists(CONFIG_FILE):
                        with open(CONFIG_FILE, 'r') as f:
                            configs_data = f.read()
                        
                        st.download_button(
                            label="💾 Download Configurations",
                            data=configs_data,
                            file_name=f"zendesk_ada_configs_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                            mime="application/json",
                            key="download_configs_btn"
                        )
                except Exception as e:
                    st.error(f"Export failed: {str(e)}")
        
        with col2:
            uploaded_file = st.file_uploader("📁 Import Configurations", type="json", key="import_configs_upload")
            if uploaded_file is not None:
                try:
                    imported_configs = json.load(uploaded_file)
                    
                    existing_configs = {}
                    if os.path.exists(CONFIG_FILE):
                        with open(CONFIG_FILE, 'r') as f:
                            existing_configs = json.load(f)
                    
                    existing_configs.update(imported_configs)
                    
                    with open(CONFIG_FILE, 'w') as f:
                        json.dump(existing_configs, f, indent=2)
                    
                    load_all_configs_to_session()
                    st.success(f"✅ Imported {len(imported_configs)} configuration(s)!")
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Import failed: {str(e)}")

# Zendesk Configuration
st.subheader("Zendesk Configuration")
st.text_input("Zendesk Subdomain (e.g., paulaschoice)", key='zd_subdomain')
st.text_input("Zendesk Email (required for restricted articles)", key='zd_email')
st.text_input("Zendesk API Token (required for restricted articles)", type="password", key='zd_token')

# Ada Configuration  
st.subheader("Ada Configuration")
st.text_input("Ada Bot Handle (e.g., 'mycompany' from mycompany.ada.support)", key='ada_subdomain')
st.text_input("Ada Knowledge API Token", type="password", key='ada_api_token')

# Access Options
st.subheader("Access Options")
st.checkbox("Include articles behind login", key='include_restricted')

# Get values from session state
include_restricted = st.session_state.get('include_restricted', True)
zd_email = st.session_state.get('zd_email', '')
zd_token = st.session_state.get('zd_token', '')
zd_subdomain = st.session_state.get('zd_subdomain', '')

if include_restricted and (not zd_email or not zd_token):
    st.warning("⚠️ Zendesk email and API token required for restricted articles")

# Filter options
st.subheader("Filtering Options")
st.write("Enable/disable filters and select specific options")

col1, col2 = st.columns(2)

with col1:
    if st.button('Load Filter Options', key="load_filters_btn"):
        if zd_subdomain and ((not include_restricted) or (zd_email and zd_token)):
            with st.spinner("Loading filter options..."):
                locales = get_locales()
                brands = get_brands()
                categories = get_categories()
                sections = get_sections()
                
                st.session_state['locales'] = locales
                st.session_state['brands'] = brands
                st.session_state['categories'] = categories
                st.session_state['sections'] = sections
                
                st.success("Filter options loaded successfully!")
        else:
            st.error("Please provide required configuration first")

with col2:
    selected_locales = None
    selected_brands = None  
    selected_categories = None
    
    # Locale Filter
    if 'locales' in st.session_state:
        use_locale_filter = st.checkbox("Enable Locale Filter", key="use_locale_filter")
        if use_locale_filter:
            locale_options = st.session_state['locales']
            locale_selections = st.multiselect(
                "Select Locales", 
                options=locale_options,
                help="Select specific locales to filter by",
                key="locale_multiselect"
            )
            if locale_selections:
                selected_locales = locale_selections
        else:
            st.info("Locale filter disabled - will not fetch by locale")
    
    # Brand Filter
    if 'brands' in st.session_state:
        use_brand_filter = st.checkbox("Enable Brand Filter", key="use_brand_filter")
        if use_brand_filter:
            brand_options = [(brand['name'], brand['id']) for brand in st.session_state['brands']]
            selected_brand_names = st.multiselect(
                "Select Brands", 
                options=[name for name, _ in brand_options],
                help="Select specific brands to filter by",
                key="brand_multiselect"
            )
            if selected_brand_names:
                selected_brands = [brand_id for name, brand_id in brand_options if name in selected_brand_names]
        else:
            st.info("Brand filter disabled - will not fetch by brand")
    
    # Category Filter
    if 'categories' in st.session_state:
        use_category_filter = st.checkbox("Enable Category Filter", key="use_category_filter")
        if use_category_filter:
            category_options = [(cat['name'], cat['id']) for cat in st.session_state['categories']]
            selected_category_names = st.multiselect(
                "Select Categories", 
                options=[name for name, _ in category_options],
                help="Select specific categories to filter by",
                key="category_multiselect"
            )
            if selected_category_names:
                selected_categories = [cat_id for name, cat_id in category_options if name in selected_category_names]
        else:
            st.info("Category filter disabled - will not fetch by category")

# Brand-Subdomain Mapping Table
if 'brands' in st.session_state and st.session_state['brands']:
    with st.expander("🏢 Brand → Subdomain Mapping", expanded=False):
        st.write("**Mapping between brands and their Help Center subdomains:**")
        
        brand_mapping_data = []
        for brand in st.session_state['brands']:
            brand_base_url = get_brand_base_url(brand)
            help_center_url = f"{brand_base_url}/hc"
            api_base_url = f"{brand_base_url}/api/v2/help_center"
            
            brand_mapping_data.append({
                "Brand Name": brand['name'],
                "Brand ID": brand['id'],
                "Zendesk Subdomain": brand.get('subdomain', 'N/A'),
                "Custom Domain": brand.get('host_mapping', 'None'),
                "Help Center URL": help_center_url,
                "API Base URL": api_base_url,
                "Uses Custom Domain": "✅ Yes" if brand.get('host_mapping') else "❌ No"
            })
        
        brands_df = pd.DataFrame(brand_mapping_data)
        
        st.dataframe(
            brands_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Help Center URL": st.column_config.LinkColumn("Help Center URL"),
                "Brand ID": st.column_config.NumberColumn("Brand ID", format="%d"),
            }
        )
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Brands", len(st.session_state['brands']))
        with col2:
            custom_domains = sum(1 for brand in st.session_state['brands'] if brand.get('host_mapping'))
            st.metric("Custom Domains", custom_domains)
        with col3:
            zendesk_subdomains = len(st.session_state['brands']) - custom_domains
            st.metric("Zendesk Subdomains", zendesk_subdomains)
        
        if st.button("📥 Download Brand Mapping", key="download_brand_mapping_btn"):
            brands_json = json.dumps(brand_mapping_data, indent=2)
            st.download_button(
                label="Download Brand Mapping JSON",
                data=brands_json,
                file_name=f"brand_mapping_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_brand_mapping_file_btn"
            )

# Article Fetching Section
st.subheader("Article Fetching")

can_fetch = (zd_subdomain and ((not include_restricted) or (zd_email and zd_token)))

if not can_fetch:
    st.info("Complete Zendesk configuration above to enable article fetching")

# Show current filter selection
if can_fetch:
    filter_summary = []
    
    if selected_locales:
        filter_summary.append(f"Locales: {', '.join(selected_locales)}")
        
    if selected_brands:
        brand_names = [name for name, brand_id in [(brand['name'], brand['id']) for brand in st.session_state.get('brands', [])] if brand_id in selected_brands]
        filter_summary.append(f"Brands: {', '.join(brand_names)}")
        
    if selected_categories:
        cat_names = [name for name, cat_id in [(cat['name'], cat['id']) for cat in st.session_state.get('categories', [])] if cat_id in selected_categories]
        filter_summary.append(f"Categories: {', '.join(cat_names)}")
    
    if filter_summary:
        st.info(f"**Active filters:** {' | '.join(filter_summary)}")
    else:
        st.warning("⚠️ **No filters selected** - Please enable and select at least one filter to fetch articles")

# Fetch Articles Button
if st.button('Fetch Articles from Zendesk', disabled=not can_fetch, key="fetch_articles_btn"):
    if not is_valid_subdomain(zd_subdomain):
        st.error("The provided Zendesk Subdomain is not valid.")
    else:
        with st.spinner("Fetching articles from Zendesk..."):
            articles = fetch_articles_with_filters(
                selected_locales=selected_locales,
                selected_brands=selected_brands,
                selected_categories=selected_categories
            )
            
            if articles:
                st.session_state['fetched_articles'] = articles
                st.success(f"Successfully fetched {len(articles)} articles from Zendesk!")
            else:
                st.warning("No articles found with the current filters.")

# Display fetched articles preview
if 'fetched_articles' in st.session_state:
    st.subheader("Fetched Articles Preview")
    st.write(f"**Total articles found:** {len(st.session_state['fetched_articles'])}")
    
    col1, col2, col3, col4 = st.columns(4)
    articles = st.session_state['fetched_articles']
    
    with col1:
        locales = set(article.get('locale', 'N/A') for article in articles)
        st.metric("Languages", len(locales))
    
    with col2:
        brands = set(article.get('_brand_name', article.get('brand_id', 'N/A')) for article in articles)
        st.metric("Brands", len(brands))
    
    with col3:
        sections = set(article.get('section_id', 'N/A') for article in articles)
        st.metric("Sections", len(sections))
    
    with col4:
        published = sum(1 for article in articles if article.get('draft', True) is False)
        st.metric("Published", published)
    
    with st.expander("📋 Article Details", expanded=False):
        search_term = st.text_input("🔍 Search articles", placeholder="Search by title...", key="article_search")
        
        filtered_articles = articles
        if search_term:
            filtered_articles = [
                article for article in articles 
                if search_term.lower() in article.get('title', '').lower()
            ]
        
        st.write(f"Showing {len(filtered_articles)} of {len(articles)} articles")
        
        for i, article in enumerate(filtered_articles[:20]):
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"**{i+1}. {article.get('title', 'No Title')}**")
                    brand_display = article.get('_brand_name', article.get('brand_id', 'N/A'))
                    brand_url = article.get('_brand_url', 'N/A')
                    st.write(f"🌐 Locale: {article.get('locale', 'N/A')} | 🏢 Brand: {brand_display} | 📂 Section: {article.get('section_id', 'N/A')}")
                    
                    # Show corrected URL
                    original_url = article.get('html_url', '')
                    if original_url and brand_url != 'N/A':
                        parsed_url = urllib.parse.urlparse(original_url)
                        corrected_url = f"{brand_url}{parsed_url.path}"
                        st.write(f"📄 Original URL: {original_url}")
                        st.write(f"✅ Corrected URL: {corrected_url}")
                        display_url = corrected_url
                    elif original_url:
                        st.write(f"📄 URL: {original_url}")
                        display_url = original_url
                    else:
                        display_url = None
                        
                with col2:
                    if display_url:
                        # Use markdown link instead of st.link_button
                        st.markdown(f"[🔗 View Article]({display_url})")
                st.divider()
        
        if len(filtered_articles) > 20:
            st.info(f"... and {len(filtered_articles) - 20} more articles. Use search to find specific articles.")
    
    if st.button("📥 Download Articles as JSON", key="download_articles_btn"):
        articles_json = json.dumps(st.session_state['fetched_articles'], indent=2)
        st.download_button(
            label="Download Articles JSON",
            data=articles_json,
            file_name=f"zendesk_articles_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            key="download_articles_file_btn"
        )

# Knowledge Source Selection
if 'fetched_articles' in st.session_state:
    st.subheader("Knowledge Source Selection")
    st.write("Now select where to upload these articles in Ada")
    
    ada_subdomain = st.session_state.get('ada_subdomain', '')
    ada_api_token = st.session_state.get('ada_api_token', '')
    
    use_existing_source = st.radio(
        "Choose knowledge source option:",
        ["Use existing knowledge source", "Create new knowledge source"],
        key="knowledge_source_radio"
    )

    selected_source_id = None

    if use_existing_source == "Use existing knowledge source":
        if st.button("Load Existing Knowledge Sources", key="load_knowledge_sources_btn"):
            if ada_subdomain and ada_api_token:
                existing_sources = get_existing_knowledge_sources()
                if existing_sources:
                    st.session_state['available_sources'] = existing_sources
                    st.success("Knowledge sources loaded successfully!")
            else:
                st.error("Please provide Ada configuration first")
        
        if 'available_sources' in st.session_state:
            source_options = {f"{source['name']} (ID: {source['id']})": source['id'] 
                             for source in st.session_state['available_sources']}
            
            if source_options:
                selected_display = st.selectbox("Select Knowledge Source:", list(source_options.keys()), key="knowledge_source_selector")
                selected_source_id = source_options[selected_display]
            else:
                st.info("No knowledge sources found")
            
    elif use_existing_source == "Create new knowledge source":
        new_source_name = st.text_input("Knowledge Source Name", "", key="new_source_name_input")
        if st.button("Create Knowledge Source", key="create_knowledge_source_btn"):
            if new_source_name and ada_subdomain and ada_api_token:
                selected_source_id = create_knowledge_source_with_random_id(new_source_name)
                if selected_source_id:
                    st.success(f"Created knowledge source '{new_source_name}' with ID: {selected_source_id}")
            else:
                st.error("Please provide knowledge source name and Ada configuration")

    # Ada Payload Preview
    if selected_source_id:
        st.subheader("Ada Payload Preview")
        st.write("Preview of how articles will be formatted for Ada API")
        
        sample_articles = st.session_state['fetched_articles'][:3]
        formatted_sample = format_articles_for_ada(sample_articles, selected_source_id)
        
        with st.expander("Sample Ada API Payload (first 3 articles)"):
            payload_preview = []
            for article in formatted_sample['articles']:
                preview_article = {**article}
                if len(preview_article['content']) > 200:
                    preview_article['content'] = preview_article['content'][:200] + "... [truncated for preview]"
                payload_preview.append(preview_article)
            
            st.json(payload_preview)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            total_size = sum(len(json.dumps(article).encode('utf-8')) for article in formatted_sample['articles'])
            st.metric("Total Payload Size", f"{total_size:,} bytes")
        with col2:
            if formatted_sample['articles']:
                avg_content_length = sum(len(article['content']) for article in formatted_sample['articles']) / len(formatted_sample['articles'])
                st.metric("Avg Content Length", f"{avg_content_length:.0f} chars")
        with col3:
            languages = set(article['language'] for article in formatted_sample['articles'])
            st.metric("Languages", len(languages))
        
        if st.button("Download Full Ada Payload as JSON", key="download_ada_payload_btn"):
            full_formatted = format_articles_for_ada(st.session_state['fetched_articles'], selected_source_id)
            payload_json = json.dumps(full_formatted['articles'], indent=2)
            st.download_button(
                label="Download Payload JSON",
                data=payload_json,
                file_name=f"ada_payload_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key="download_ada_payload_file_btn"
            )

        upload_ready = 'fetched_articles' in st.session_state and selected_source_id
        if st.button('🚀 Upload Articles to Ada', disabled=not upload_ready, key="upload_articles_btn"):
            with st.spinner("Uploading articles to Ada..."):
                formatted_articles = format_articles_for_ada(st.session_state['fetched_articles'], selected_source_id)
                upload_articles_to_ada(formatted_articles)
                total_uploaded = len(formatted_articles['articles'])
                
                st.success(f"🎉 Upload completed! Total articles uploaded: {total_uploaded}")
                
                if 'fetched_articles' in st.session_state:
                    del st.session_state['fetched_articles']

# API Logs Section
st.subheader("API Logs")
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    if st.button("Clear Logs", key="clear_logs_btn"):
        clear_logs()
        st.rerun()

with col2:
    show_payloads = st.checkbox("Show Payloads", value=False, key="show_payloads_checkbox")

with col3:
    log_filter = st.selectbox("Filter by Status", ["All", "SUCCESS", "ERROR", "WARNING", "INFO"], key="log_filter_selector")

if st.session_state.get('api_logs'):
    logs_df = pd.DataFrame(st.session_state['api_logs'])
    
    if log_filter != "All":
        logs_df = logs_df[logs_df['status'] == log_filter]
    
    if show_payloads:
        display_columns = ['timestamp', 'action', 'status', 'endpoint', 'request', 'response', 'details']
    else:
        display_columns = ['timestamp', 'action', 'status', 'endpoint', 'details']
        logs_df = logs_df[display_columns]
    
    def style_status(val):
        if val == "SUCCESS":
            return "background-color: #d4edda; color: #155724"
        elif val == "ERROR":
            return "background-color: #f8d7da; color: #721c24"
        elif val == "WARNING":
            return "background-color: #fff3cd; color: #856404"
        else:
            return "background-color: #d1ecf1; color: #0c5460"
    
    logs_df = logs_df.iloc[::-1].reset_index(drop=True)
    
    st.dataframe(
        logs_df.style.applymap(style_status, subset=['status']),
        use_container_width=True,
        height=400,
        hide_index=True
    )
    
    if st.button("Download Logs as JSON", key="download_logs_btn"):
        logs_json = json.dumps(st.session_state['api_logs'], indent=2)
        st.download_button(
            label="Download JSON",
            data=logs_json,
            file_name=f"api_logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            key="download_logs_file_btn"
        )
else:
    st.info("No API calls logged yet. Logs will appear here when you start fetching or uploading articles.")