#!/bin/bash

jq -c '.[]' conversations.json | while read -r convo; do
  # pull the title
  title=$(echo "$convo" | jq -r '.title' | tr ' /' '_' | tr -cd '[:alnum:]_')
  if [ -z "$title" ]; then
    title="untitled"
  fi

  # grab first message timestamp (fallback to convo create_time)
  ts=$(echo "$convo" | jq -r '
    (
      .messages[0].create_time // .create_time // "no_time"
    )
  ')

  # make timestamp filename-safe: replace ":" with "-", keep Z if present
  safe_ts=$(echo "$ts" | sed 's/:/-/g' | sed 's/ /_/g')

  # build filename
  filename="${safe_ts}__${title}.json"

  # write the convo object to that file, pretty-printed (not one-line)
  echo "$convo" | jq '.' > "$filename"
done
