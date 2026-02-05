import asyncio
from database.initialization import AsyncSessionLocal
from database.schemas import SkillModel

async def seed_skills():
    skills = [
        # Audio
        {"name": "Audio Engineering", "category": "Audio"},
        {"name": "Sound Design", "category": "Audio"},
        {"name": "Music Composition", "category": "Audio"},
        {"name": "Foley Artist", "category": "Audio"},
        
        # Video
        {"name": "Cinematography", "category": "Video"},
        {"name": "Camera Operator", "category": "Video"},
        {"name": "Video Editing", "category": "Video"},
        {"name": "Color Grading", "category": "Video"},
        {"name": "Drone Operator", "category": "Video"},
        
        # Lighting
        {"name": "Lighting Technician", "category": "Lighting"},
        {"name": "Gaffer", "category": "Lighting"},
        {"name": "Best Boy Electric", "category": "Lighting"},
        
        # Production
        {"name": "Director", "category": "Production"},
        {"name": "Producer", "category": "Production"},
        {"name": "Assistant Director", "category": "Production"},
        {"name": "Production Manager", "category": "Production"},
        {"name": "Script Supervisor", "category": "Production"},
        
        # Art & Design
        {"name": "Production Designer", "category": "Art"},
        {"name": "Art Director", "category": "Art"},
        {"name": "Set Designer", "category": "Art"},
        {"name": "Props Master", "category": "Art"},
        {"name": "Costume Designer", "category": "Art"},
        {"name": "Makeup Artist", "category": "Art"},
        
        # Post-Production
        {"name": "Editor", "category": "Post-Production"},
        {"name": "VFX Artist", "category": "Post-Production"},
        {"name": "Motion Graphics", "category": "Post-Production"},
        {"name": "Compositor", "category": "Post-Production"},
        
        # Acting
        {"name": "Actor", "category": "Acting"},
        {"name": "Voice Actor", "category": "Acting"},
        {"name": "Stunt Performer", "category": "Acting"},
        
        # Other
        {"name": "Screenwriter", "category": "Writing"},
        {"name": "Location Scout", "category": "Other"},
        {"name": "Casting Director", "category": "Other"},
    ]
    
    async with AsyncSessionLocal() as db:
        for skill_data in skills:
            skill = SkillModel(**skill_data)
            db.add(skill)
        
        await db.commit()
        print(f"✅ Seeded {len(skills)} skills!")

if __name__ == "__main__":
    asyncio.run(seed_skills())

'''
**Quick reference of your skill IDs:**
```
Audio:
1  - Audio Engineering
2  - Sound Design
3  - Music Composition
4  - Foley Artist

Video:
5  - Cinematography
6  - Camera Operator
7  - Video Editing
8  - Color Grading
9  - Drone Operator

Lighting:
10 - Lighting Technician
11 - Gaffer
12 - Best Boy Electric

Production:
13 - Director
14 - Producer
15 - Assistant Director
16 - Production Manager
17 - Script Supervisor

Art:
18 - Production Designer
19 - Art Director
20 - Set Designer
21 - Props Master
22 - Costume Designer
24 - Makeup Artist

Post-Production:
25 - Editor
26 - VFX Artist
27 - Motion Graphics
28 - Compositor

Acting:
29 - Actor
30 - Voice Actor
31 - Stunt Performer

Other:
32 - Screenwriter
33 - Location Scout
34 - Casting Director
'''