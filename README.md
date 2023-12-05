# Usage

```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt 

cp -i secrets.yml.j2 secrets.yml
# get user API_KEY from https://app.clockify.me/user/settings
nano secrets.yml

# -n == dry-run
./mk-lunch.py 2023 11 -n
```
