# Home Internet setup

The server is configured for Internet mode (`sv_lan 0`) with Steam authentication, an empty game password and masterserver participation. The old `-nomaster` and `-insecure` flags are absent. Check actual Steam/VAC status in the running server console; configuration alone is not verification.

## Router and firewall

1. Find the Mint laptop's LAN IPv4 using your router or `ip -4 addr`. Assign it a DHCP reservation in the router so port forwarding remains valid.
2. Forward **UDP 27015** to that laptop and port. If setup used another port, use it consistently. The public IPv4 belongs on the router, not in HLDS's local `+ip` setting.
3. Check `sudo ufw status`. If UFW is active, add the selected game port, for example `sudo ufw allow 27015/udp`. Setup does not enable or change the firewall automatically.
4. Keep outbound Internet/DNS access available for Steam authentication and masterservers. See [Valve's port reference](https://help.steampowered.com/en/faqs/view/2EA8-4D75-DA21-31EB). Its SRCDS TCP RCON entry concerns Source servers; this GoldSrc panel uses UDP RCON on the game endpoint.

Do not forward the browser-panel port. Public gameplay and queries share the game UDP endpoint. RCON uses a generated long password; use local panel administration and keep that password private. No broad port range or router DMZ is required for this setup.

## Check your connection type

The router needs a directly reachable public IPv4, or a forwarding arrangement through every upstream NAT. With DS-Lite/CGNAT, a port forward on your home router alone cannot normally provide inbound IPv4 access. Check the router's WAN information and your ISP's connection details. Addresses in `100.64.0.0/10` or private IPv4 ranges indicate upstream address translation. Resolve this with your ISP before expecting a direct public IPv4 connection.

If your public address changes, tell players the new address or configure a hostname through your router's dynamic-DNS feature. Dynamic DNS does not bypass CGNAT.

## Verify in this order

1. Start the server and inspect `version`, `status`, `meta list`, `amxx plugins` and `amxx modules`. Check Steam login and VAC messages. Look for plugin load errors.
2. From the laptop, run `python3 scripts/server_query.py 127.0.0.1 --port 27015`. For an explicit LAN bind, query that LAN address instead. This establishes only local responsiveness.
3. Join from a Steam CS 1.6 client on your LAN: `connect <laptop-LAN-IP>:27015`.
4. Have a Steam client on a **different Internet connection** join with `connect <public-IPv4-or-hostname>:27015`. A Steam server entry in Favorites can also query the endpoint.
5. Check Steam's Internet server list separately. Listing may take time and is not the same check as direct connection.
6. Repeat after a server restart; test downloading a custom map and sound resources on a client without them.

A public-address test from inside the same LAN can fail because of missing router NAT loopback even when outside players can join. Generic web TCP port checkers do not establish whether this UDP game server is reachable. Record actual external-client results.
