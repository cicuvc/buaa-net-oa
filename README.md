## BUAA campus network always online daemon

A daemon for automatically maintain connectivity and authentication with the campus network, 
automatically detect and troubleshoot faults in the event of a network outage to attempt to 
restore connectivity, and update the latest LAN IP to Cloudflare KV storage.

Because there is no wired network interface in the new dormitory, the servers in the dormitory 
will only be able to obtain network connection and remote control through the campus network. 
To solve instable issues and dynamic IP changes of WiFi, we write this daemon

Daemon consists of 4 parts
- Network Status Detection
- SRUN Authentication Client
- WPA Client
- Cloudflare KV Client