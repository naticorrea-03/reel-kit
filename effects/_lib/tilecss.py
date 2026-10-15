"""prints the shared tile CSS for one effect id: python3 effects/_lib/tilecss.py <id> (pasted into effects/<id>/style.css)."""
import sys
X = '.fx-' + sys.argv[1]
print(f'''{X} .tl{{position:absolute;transform-origin:50% 50%;will-change:transform,opacity}}
{X} .cd{{position:absolute;inset:0;border-radius:calc(var(--card-radius) * .7);overflow:hidden;background:var(--c-card);
  border:calc(var(--card-border) * .5) solid var(--c-frame);box-shadow:0 22px 48px color-mix(in srgb,var(--c-shadow) 42%,transparent)}}
{X} .im{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
{X} .lb{{position:absolute;left:0;right:0;bottom:0;padding:22% 8% 9%;background:linear-gradient(180deg,transparent,color-mix(in srgb,var(--c-shadow) 78%,transparent))}}
{X} .lt{{color:var(--c-text);font-family:var(--f-display);font-weight:800;line-height:1.04;letter-spacing:-.02em;overflow-wrap:anywhere}}
{X} .tg{{position:absolute;inset:0;padding:9% 8%;display:flex;flex-direction:column;gap:.35em;color:var(--c-text)}}
{X} .tg.v0{{background:var(--c-card);color:var(--c-ink)}}
{X} .tg.v1{{background:linear-gradient(160deg,var(--c-accent),color-mix(in srgb,var(--c-accent) 70%,var(--c-ink)))}}
{X} .tg.v2{{background:var(--c-soft);color:var(--c-ink)}}
{X} .tg.v3{{background:linear-gradient(160deg,var(--c-accent2),color-mix(in srgb,var(--c-accent2) 70%,var(--c-ink)))}}
{X} .tg.v0 .kk,{X} .tg.v2 .kk{{color:var(--c-accent-ink)}}
{X} .kk{{font-family:var(--f-mono);font-weight:600;letter-spacing:.06em;color:color-mix(in srgb,currentColor 75%,transparent)}}
{X} .tt{{font-family:var(--f-display);font-weight:800;line-height:1.02;letter-spacing:-.025em;margin-top:auto;overflow-wrap:anywhere}}
{X} .sb{{font-family:var(--f-body);font-weight:500;line-height:1.2;color:color-mix(in srgb,currentColor 85%,transparent);overflow-wrap:anywhere}}
{X} .vl{{position:absolute;inset:0;border-radius:calc(var(--card-radius) * .7);background:var(--c-shadow);opacity:0;pointer-events:none}}''')
