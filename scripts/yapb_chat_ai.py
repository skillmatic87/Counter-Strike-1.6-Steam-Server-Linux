"""Apply the server's directed-chat changes to the pinned YaPB AMXX sample."""


ADDRESS_LOOKUP = r'''// Return the complete bot name at the address position, preferring the
// longest match when one bot's full name is a prefix of another's.
find_bot_at (sender, const text[], bool:team_only, &name_length) {
  new name[32], best;
  name_length = 0;

  for (new id = 1; id <= get_maxplayers (); ++id) {
    if (id == sender || !is_user_connected (id) || !yb_is_user_bot (id) || yb_is_bot_stale (id)) {
      continue;
    }
    if (team_only && get_user_team (id) != get_user_team (sender)) {
      continue;
    }
    if (yb_get_bot_chat (id) == YB_CHAT_OFF) {
      continue;
    }

    get_user_name (id, name, charsmax (name));
    new size = strlen (name);

    if (size > name_length && equali (text, name, size) &&
        (text[size] == EOS || is_address_separator (text[size]))) {
      best = id;
      name_length = size;
    }
  }
  return best;
}

bool:is_address_separator (ch) {
  return ch == ' ' || ch == ',' || ch == ':' || ch == ';' ||
    ch == '!' || ch == '?' || ch == '.';
}

find_addressed_bot (sender, const raw[], bool:team_only, output[], length) {
  new text[CHAT_TEXT_SIZE];
  copy (text, charsmax (text), raw);
  // GoldSrc forwards the whole say argument, including its enclosing quotes.
  trim (text);
  remove_quotes (text);
  trim (text);

  new name_length, start;
  new bot = find_bot_at (sender, text, team_only, name_length);

  if (!bot) {
    new const greetings[][] = {"hi", "hey", "hello", "yo", "sup"};

    for (new i = 0; i < sizeof greetings; ++i) {
      new size = strlen (greetings[i]);

      if (!equali (text, greetings[i], size) || !is_address_separator (text[size])) {
        continue;
      }
      start = size;
      while (is_address_separator (text[start])) {
        ++start;
      }
      bot = find_bot_at (sender, text[start], team_only, name_length);
      break;
    }
  }
  if (!bot) {
    return 0;
  }

  new offset = start + name_length;
  while (is_address_separator (text[offset])) {
    ++offset;
  }
  copy (output, length, text[offset]);
  if (!output[0]) {
    copy (output, length, "Hello!");
  }
  return bot;
}

// Team-only answers are discarded if either participant has changed teams.
// Userids prevent delivery to a new connection occupying the same slot.
bool:direct_target_current () {
  return is_user_connected (g_sender) && !is_user_bot (g_sender) &&
    get_user_userid (g_sender) == g_direct_sender &&
    is_user_connected (g_bot) && get_user_userid (g_bot) == g_direct_bot &&
    (!g_team_only || (get_user_team (g_sender) == g_direct_team && get_user_team (g_bot) == g_direct_team));
}

'''


def patch_chat_ai_source(path):
    source = path.read_text(encoding='utf-8')

    def replace(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError(f'The pinned YaPB Chat AI source has changed near {old.splitlines()[0]!r}.')
        source = source.replace(old, new)

    begin = source.index('find_addressed_bot (sender, const message[]')
    end = source.index('find_chat_bot (sender, bool:team_only', begin)
    source = source[:begin] + ADDRESS_LOOKUP + source[end:]
    replace('  rq_prompt,\n', '  rq_prompt,\n  rq_direct_sender,\n  rq_direct_bot,\n  rq_direct_team,\n')
    replace('new g_prompt;\n', 'new g_prompt;\nnew g_direct_sender, g_direct_bot, g_direct_team;\n')
    replace('  new bot;\n  new text[CHAT_TEXT_SIZE];',
            '  new bot;\n  new bool:addressed;\n  new text[CHAT_TEXT_SIZE];')
    replace('      bot = find_addressed_bot (sender, message, team_only, bool:alive, text, charsmax (text), !bool:alive);',
            '      addressed = true;\n'
            '      bot = find_addressed_bot (sender, message, team_only, text, charsmax (text));')
    replace('!queue_reply (sender, bot, text, team_only, prompt, false)',
            '!queue_reply (sender, bot, text, team_only, prompt, false, addressed)')
    replace('queue_reply (sender, bot, const text[], bool:team_only, prompt, bool:followup) {',
            'queue_reply (sender, bot, const text[], bool:team_only, prompt, bool:followup, bool:addressed = false) {')
    replace('  g_queue[slot][rq_prompt] = prompt;\n', '''  g_queue[slot][rq_prompt] = prompt;
  g_queue[slot][rq_direct_sender] = addressed ? get_user_userid (sender) : 0;
  g_queue[slot][rq_direct_bot] = addressed ? get_user_userid (bot) : 0;
  g_queue[slot][rq_direct_team] = addressed && team_only ? get_user_team (sender) : 0;
''')
    replace('  g_prompt = g_queue[0][rq_prompt];\n', '''  g_prompt = g_queue[0][rq_prompt];
  g_direct_sender = g_queue[0][rq_direct_sender];
  g_direct_bot = g_queue[0][rq_direct_bot];
  g_direct_team = g_queue[0][rq_direct_team];
''')
    replace('  g_queue[dest][rq_prompt] = g_queue[src][rq_prompt];\n', '''  g_queue[dest][rq_prompt] = g_queue[src][rq_prompt];
  g_queue[dest][rq_direct_sender] = g_queue[src][rq_direct_sender];
  g_queue[dest][rq_direct_bot] = g_queue[src][rq_direct_bot];
  g_queue[dest][rq_direct_team] = g_queue[src][rq_direct_team];
''')
    replace('  get_pcvar_string (g_cvar_url, g_url, charsmax (g_url));', '''  if (g_direct_sender && !direct_target_current ()) {
    return false;
  }

  get_pcvar_string (g_cvar_url, g_url, charsmax (g_url));''')
    replace('  for (new i = 0; i < g_history_count[g_bot]; ++i) {',
            '  // Private conversations use only the current message.\n'
            '  new history_count = g_direct_sender ? 0 : g_history_count[g_bot];\n'
            '  for (new i = 0; i < history_count; ++i) {')
    replace('  new bot = g_bot;\n', '''  new bot = g_bot;
  new sender = g_sender;
  new bool:direct = g_direct_sender != 0;
  new bool:deliver_direct = direct && direct_target_current ();
''')
    replace('    yb_bot_say (bot, reply, team_only, true);', r'''    if (direct) {
      if (deliver_direct) {
        new name[32];
        get_user_name (bot, name, charsmax (name));
        // SayText has a smaller limit than the model's configurable reply buffer.
        reply[150] = EOS;
        new printed = client_print_color (sender, bot, "^3%s^1: %s", name, reply);
        ai_log ("DIRECT delivered sender=%d bot=%d chars=%d", sender, bot, printed);
      }
      pump_queue ();
      return;
    }
    yb_bot_say (bot, reply, team_only, true);''')
    replace('  g_prompt = 0;\n', '''  g_prompt = 0;
  g_direct_sender = 0;
  g_direct_bot = 0;
  g_direct_team = 0;
''')
    path.write_text(source, encoding='utf-8', newline='\n')
