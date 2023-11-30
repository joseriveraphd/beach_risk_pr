mkdir -p ~/.streamlit/

echo "\
[theme]
base='light'
[server]\n\
headless = true\n\
enableCORS=false\n\
port = $PORT\n\
" > ~/.streamlit/config.toml