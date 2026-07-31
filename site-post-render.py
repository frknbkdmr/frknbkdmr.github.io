"""Run the existing post-render fixes, then apply the site's crawler policy.

Search engines and user-initiated AI retrieval remain welcome. Crawlers whose
stated purpose includes model training or general model development are blocked.
Keeping this as the final post-render step prevents Quarto or post-render.py from
silently restoring the previous site-wide training permission.
"""

import re
import subprocess
import sys