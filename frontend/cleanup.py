import re

with open('src/app/page.tsx', 'r') as f:
    content = f.read()

# Remove decorative background circles
content = re.sub(r'<div className="absolute top-.*?\n', '', content)
content = re.sub(r'\s*<div className="absolute bottom-.*?\n', '', content)

# Remove text gradients
content = content.replace('bg-clip-text text-transparent bg-gradient-to-r from-slate-800 to-slate-600', 'text-slate-900')
content = content.replace('bg-clip-text bg-gradient-to-r from-orange-500 to-slate-700 text-transparent', 'text-slate-900')
content = content.replace('text-transparent bg-clip-text bg-gradient-to-r from-orange-500 to-slate-700', 'text-slate-900')
content = content.replace('bg-gradient-to-br from-orange-500 to-slate-800', 'bg-orange-500')

# Emerald -> Slate-900 (Black)
content = content.replace('emerald-500', 'slate-900')
content = content.replace('emerald-400', 'slate-900')
content = content.replace('emerald-300', 'slate-900')

# Fuchsia -> Orange
content = content.replace('fuchsia-500', 'orange-500')
content = content.replace('fuchsia-400', 'orange-500')
content = content.replace('fuchsia-300', 'orange-500')

# Amber -> Orange
content = content.replace('amber-500', 'orange-500')
content = content.replace('amber-400', 'orange-500')

# Rose -> Red
content = content.replace('rose-500', 'red-500')
content = content.replace('rose-400', 'red-500')
content = content.replace('rose-300', 'red-500')

with open('src/app/page.tsx', 'w') as f:
    f.write(content)
print('Cleaned up colors.')
