import csv
import json
from datetime import datetime

def csv_to_quads(csv_file, output_file):
    quads = []
    
    with open(csv_file, 'r') as file:
        csv_reader = csv.DictReader(file)
        
        for row in csv_reader:
            player_name = row['NAME']
            team = row['TEAM']
            position = row['POS']
            
            # Create quads for each statistic
            for key, value in row.items():
                if key not in ['RANK', 'NAME', 'TEAM', 'POS', 'AGE', 'GP']:
                    quad = [
                        player_name,
                        f"has_{key.lower()}",
                        value,
                        f"NBA_2023_regular_season"
                    ]
                    quads.append(quad)
            
            # Additional quads for team and position
            quads.append([player_name, "plays_for", team, "NBA_2023_regular_season"])
            quads.append([player_name, "plays_as", position, "NBA_2023_regular_season"])
    
    # Save quads to a JSON Lines file
    with open(output_file, 'w') as f:
        for quad in quads:
            f.write(json.dumps(quad) + '\n')

    print(f"Conversion complete. Quads saved to {output_file}")

# Usage
csv_file = 'raw_data/nba-stats-2023.csv'
output_file = 'raw_data/nba_stats_2023_quads.jsonl'
csv_to_quads(csv_file, output_file)