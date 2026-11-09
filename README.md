## Server for WemosEBell instances

Runs on a RaspberryPi, listening on UDP port 5005.  Accepts registration messages via any network route, although WemosEBell clients will first connect to a wifi SSID offered by the RaspberryPi.

Registers up to 12 bells, assigning pitch as they are registered.

Configures local HDMI connection (this needs to be updated to support other options for sound generation).

Runs a server, listening for strike messages, then adding the sampled sound file onto the audio buffer (to support multiple bell sounds at the same time).
