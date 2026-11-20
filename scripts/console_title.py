"""Console label from public server settings only; never expose credentials."""
import re
def describe_console(command,root,game):
    port=command[command.index('-port')+1] if '-port' in command else '27015'
    directory=command[command.index('-game')+1] if '-game' in command else 'cstrike'
    try:
        text=(root/directory/'server.cfg').read_text(encoding='utf-8-sig')
        found=re.search(r'(?m)^\s*hostname\s+"([^"\r\n]+)"',text)
        name=found[1] if found else root.name
    except OSError:name=root.name
    return game+' | '+name+' | UDP '+str(port)
