from .main import main
import sys
from .utils.config_loader import load_config

def run():
    
    config = load_config()
    
    agent_id = config['agent']['agent_id']
    
    # Inject default agent_id if not provided
    if len(sys.argv) == 1:
        sys.argv.append(agent_id)  # <--- Default agent_id

    main()

if __name__ == "__main__":
    run()