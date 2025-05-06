from .main import main
import sys

# Inject default agent_id if not provided
if len(sys.argv) == 1:
    sys.argv.append("matlab")  # <-- cambia questo valore a piacere

main()
