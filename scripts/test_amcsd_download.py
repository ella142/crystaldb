search_url = (
    "https://www.rruff.net/AMS/result.php"
    f"?key=_database_code_amcsd+{amcsd_id}"
    "&viewing=html"
)

response = requests.get(
    search_url,
    headers={
        "User-Agent": (
            "crystaldb/0.1 "
            "(academic crystallography dataset project)"
        )
    },
    timeout=timeout,
    allow_redirects=True,
)

print("AMCSD request URL:", search_url)
print("HTTP status:", response.status_code)
print("Final URL:", response.url)

response.raise_for_status()