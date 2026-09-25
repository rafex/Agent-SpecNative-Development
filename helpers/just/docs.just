docs:
    bash "helpers/shell/docs.sh" --workspace "{{ workspace }}" --goal build --log-file "{{ log_file }}"

serve:
    bash "helpers/shell/docs.sh" --workspace "{{ workspace }}" --goal serve --log-file "{{ log_file }}"
