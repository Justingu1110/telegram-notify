#!/usr/bin/env bash
# Captures the raw HTML of the Marukyu-Koyamaen matcha category page and of each
# product page listed on it, to be committed as unedited test fixtures.
set -euo pipefail

BASE_URL="https://www.marukyu-koyamaen.net"
LIST_URL="${BASE_URL}/category/select/cid/312"
OUT_DIR="tests/fixtures/marukyu"
INFO_FILE="${OUT_DIR}/CAPTURE_INFO.md"
MAX_PRODUCTS=30
USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) telegram-notify-fixture-capture"

mkdir -p "${OUT_DIR}/detail"

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
  echo "# Marukyu-Koyamaen fixture capture"
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

mapfile -t pids < <(grep -oE 'pid/[0-9]+' "${list_file}" | sed 's#pid/##' | awk '!seen[$0]++')
echo "Found ${#pids[@]} product ids on the list page: ${pids[*]:-none}"
if [ "${#pids[@]}" -eq 0 ]; then
  echo "::error::No product ids found in the list page HTML; stopping."
  exit 1
fi
if [ "${#pids[@]}" -gt "${MAX_PRODUCTS}" ]; then
  echo "::warning::More than ${MAX_PRODUCTS} product ids; capturing only the first ${MAX_PRODUCTS}."
  pids=("${pids[@]:0:${MAX_PRODUCTS}}")
fi

for pid in "${pids[@]}"; do
  sleep 1
  url="${LIST_URL}/pid/${pid}"
  file="${OUT_DIR}/detail/${pid}.html"
  result="$(fetch "${url}" "${file}")"
  record "${file}" "${url}" "${result}"
done

echo
echo "== Scan for secrets or personal data =="
secret_pattern='(csrf|_token|sessionid|phpsessid)[A-Za-z_]*[" ]*[=:][ "]*[A-Za-z0-9+/=_-]{16,}'
email_pattern='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'
suspicious="$(grep -rniE -o ".{0,40}(${secret_pattern}|${email_pattern}).{0,40}" "${OUT_DIR}" --include='*.html' | grep -viE 'marukyu-koyamaen' || true)"
if [ -n "${suspicious}" ]; then
  echo "${suspicious}"
  echo "::error::Possible secrets or personal data in the captured pages; not committing. Review the matches above."
  exit 1
fi
echo "No matches."

stock_pattern='.{0,60}(库存|庫存|在庫|在库|品切|売り切れ|SOLD|缺货|缺貨).{0,60}'

echo
echo "== Language and title (list page) =="
grep -oE '<html[^>]*>' "${list_file}" | head -1 || true
grep -oE '<title>[^<]*</title>' "${list_file}" | head -1 || true

echo
echo "== Stock wording in the list page =="
grep -noE "${stock_pattern}" "${list_file}" | head -20 || true

echo
echo "== Stock wording in each detail page =="
for file in "${OUT_DIR}"/detail/*.html; do
  echo "--- ${file}"
  grep -noE "${stock_pattern}" "${file}" | head -20 || true
done
