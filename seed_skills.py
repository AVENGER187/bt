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