# X article draft

Post 1:
I reverse engineered my Hisense TV and built it a custom home screen.
No root, no firmware, no brick. Here's the whole story.

Post 2:
Every Hisense VIDAA TV speaks the RemoteNow protocol: TLS MQTT on port 36669 with a client certificate. The cert leaked years ago and everyone uses it. I grabbed it, paired my Mac with the TV through a 4-digit code, and had full control. Power, keys, apps, inputs, volume.

Post 3:
Control alone is boring. The interesting part: VIDAA has a hidden debug installer. Type `hisense://debug` in the TV Browser, give it a name and a URL, hit Install, and your web page becomes a channel on the TV. No sideloading, no store.

Post 4:
So I built a launcher. Clock, rotating 4K wallpapers, glass panels, your apps and inputs. Press OK on a tile and it actually opens the app or switches the input, through a small Python server on my Mac that bridges the page to the TV's MQTT channel.

Post 5:
First version was normal HTML/CSS. It rendered blank on the TV. The TV's browser is Chrome 77 on a weak GPU, and a dozen blurred glass layers over two 4K photos was more than it could draw. It reported zero errors. It just drew nothing.

Post 6:
The fix: throw out the DOM. The entire launcher is now a single `<canvas>` painted by JavaScript. One bitmap, one GPU layer. Everything else is smoke and mirrors: pre-blurred quarter-size photos for glass, pre-rendered shadows, only the changing strip repainted.

Post 7:
Then the performance grind. Measured on the actual TV, frame by frame:
12 fps -> 25 (baked fades, cached glow) -> 27 (partial repaint) -> 35 (render at 720p, upscale).
The TV is the constraint. You learn its rules or you lose.

Post 8:
Best part: VIDAA won't let you replace its home screen. So a 40-line Python watcher polls the TV every 3 seconds and, the moment it sees VIDAA's home, opens my launcher. Home button now lands on my UI after a one second flash of theirs.

Post 9:
Everything is open source now.
The menu bar remote: github.com/Zfinix/hisensebar
The launcher, the MQTT client and the home takeover watcher: github.com/Zfinix/vidaa-launcher

Post 10:
Full steps are in the vidaa-launcher README: get the cert, pair, run one server, install on the TV with hisense://debug, optionally take over the home screen. A Raspberry Pi would make it permanent.

Post 11:
The wallpapers are Wikimedia featured pictures (CC BY-SA, credited). The remote is SwiftUI. The TV does what I say. Next target: the Xiaomi.
