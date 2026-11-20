"""Assigned game IPv4 endpoints. Never infer a public IP or use the panel URL."""
import ipaddress,json,subprocess,sys

def endpoints(port,bind=None):
    try:
        if sys.platform=='win32':
            command=['powershell.exe','-NoProfile','-Command',"$active=@(Get-NetAdapter -IncludeHidden | Where-Object Status -eq 'Up' | Select-Object -ExpandProperty ifIndex); @(Get-NetIPAddress -AddressFamily IPv4 -AddressState Preferred | Where-Object { $_.InterfaceIndex -in $active } | Select-Object IPAddress) | ConvertTo-Json -Compress"]
            data=json.loads(subprocess.run(command,capture_output=True,text=True,check=True,timeout=5).stdout or '[]')
            records=data if isinstance(data,list) else [data]
            values=[x['IPAddress'] for x in records]
        else:
            data=json.loads(subprocess.run(['ip','-j','-4','address','show'],capture_output=True,text=True,check=True,timeout=3).stdout)
            values=[item['local'] for interface in data if 'UP' in interface.get('flags',[]) for item in interface.get('addr_info',[]) if item.get('family')=='inet']
        addresses=set()
        for value in values:
            address=ipaddress.IPv4Address(value)
            if address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast or address.is_reserved:continue
            if bind not in (None,'0.0.0.0') and str(address)!=bind:continue
            addresses.add(str(address))
        return [dict(address=value,port=int(port),connect=f'connect {value}:{port}') for value in sorted(addresses)]
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):return []
