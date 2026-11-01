#!/usr/bin/env bash
# Captures the raw HTML of the Marukyu-Koyamaen English matcha catalog page and of every
# product page linked from it, to be committed as unedited test fixtures.
set -euo pipefail

BASE_URL="https://www.marukyu-koyamaen.co.jp"
LIST_URL="${LIST_URL:-${BASE_URL}/english/shop/products/catalog/matcha/principal}"
OUT_DIR="tests/fixtures/marukyu_en"
INFO_FILE="${OUT_DIR}/CAPTURE_INFO.md"
MAX_PRODUCTS=40
USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) telegram-notify-fixture-capture"

mkdir -p "${OUT_DIR}/detail"
rm -f "${OUT_DIR}"/detail/*.html

fetch() {
  local url="$1" outfile="$2" result
  result="$(curl -sS -L --max-time 30 -A "${USER_AGENT}" -o "${outfile}" -w '%{http_code} %{content_type}' "${url}")" || result="curl-failed -"
  echo "${result}"
}

record() {
  local file="$1" url="$2" result="$3" status type bytes=0
  status="${result%% *}"
  type="${result#* }"
  if [ -f "${file}" ]; then
    bytes="$(wc -c < "${file}" | tr -d ' ')"
  fi
  echo "| ${file#"${OUT_DIR}"/} | ${url} | $(date -u +%Y-%m-%dT%H:%M:%SZ) | ${status} | ${type} | ${bytes} |" >> "${INFO_FILE}"
  echo "${url} -> HTTP ${status}, ${type}, ${bytes} bytes"
}

{
  echo "# Marukyu-Koyamaen English site fixture capture"
  echo
  echo "Raw HTML exactly as served to a GitHub Actions runner. Not edited."
  echo
  echo "| File | Source URL | Fetched at (UTC) | HTTP status | Content-Type | Bytes |"
  echo "| --- | --- | --- | --- | --- | --- |"
} > "${INFO_FILE}"

list_file="${OUT_DIR}/list.html"
result="$(fetch "${LIST_URL}" "${list_file}")"
record "${list_file}" "${LIST_URL}" "${result}"
if [ "${result%% *}" != "200" ]; then
  echo "::error::List page did not return HTTP 200 (${result}); stopping."
  exit 1
fi

mapfile -t paths < <(grep -oE '/english/shop/products/[0-9A-Za-z]{6,}' "${list_file}" | grep -v '/catalog$' | awk '!seen[$0]++')
echo "Found ${#paths[@]} product links on the list page: ${paths[*]:-none}"
if [ "${#paths[@]}" -eq 0 ]; then
  echo "::warning::No product links matched the expected pattern; only the list page was saved."
fi
if [ "${#paths[@]}" -gt "${MAX_PRODUCTS}" ]; then
  echo "::warning::More than ${MAX_PRODUCTS} product links; capturing only the first ${MAX_PRODUCTS}."
  paths=("${paths[@]:0:${MAX_PRODUCTS}}")
fi

for path in "${paths[@]}"; do
  sleep 1
  url="${BASE_URL}${path}"
  file="${OUT_DIR}/detail/${path##*/}.html"
  result="$(fetch "${url}" "${file}")"
  record "${file}" "${url}" "${result}"
  if [ "${result%% *}" != "200" ]; then
    echo "::error::Product page ${url} did not return HTTP 200 (${result}); stopping."
    exit 1
  fi
done

echo
echo "== Scan for secrets or personal data =="
secret_pattern='(csrf|_token|sessionid|phpsessid)[A-Za-z_]*[" ]*[=:][ "]*[A-Za-z0-9+/=_-]{16,}'
email_pattern='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
secret_hits="$(grep -rniE -o ".{0,40}${secret_pattern}.{0,40}" "${OUT_DIR}" --include='*.html' || true)"
email_hits="$(grep -rnoiE "${email_pattern}" "${OUT_DIR}" --include='*.html' | grep -viE '@([A-Za-z0-9-]+\.)*marukyu-koyamaen\.' || true)"
suspicious="${secret_hits}${email_hits}"
if [ -n "${suspicious}" ]; then
  echo "${suspicious}"
  echo "::error::Possible secrets or personal data in the captured pages; not committing. Review the matches above."
  exit 1
fi
echo "No matches."

echo
echo "== Title, language and availability wording (list page) =="
grep -oE '<html[^>]*>' "${list_file}" | head -1 || true
grep -oE '<title>[^<]*</title>' "${list_file}" | head -1 || true
grep -noiE '.{0,50}(out of stock|sold out|in stock|add to cart|notify me|unavailable|taiwan).{0,50}' "${list_file}" | head -30 || true
