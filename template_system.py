"""
Template System for FrogPaper

Provides reusable prompt patterns with variables for faster iterative work.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from utils import get_app_dir

logger = logging.getLogger(__name__)

BASE_DIR = get_app_dir()
TEMPLATES_FILE = BASE_DIR / "templates.json"
RECIPES_FILE = BASE_DIR / "recipes.json"
TEMPLATES_DIR = BASE_DIR / "templates"
RECIPES_DIR = BASE_DIR / "recipes"
TEMPLATES_DIR.mkdir(exist_ok=True)
RECIPES_DIR.mkdir(exist_ok=True)


def _validate_path(file_path: str | Path, allowed_dir: Path = None) -> Path:
    """Validate that a file path is within the allowed directory to prevent path traversal attacks."""
    file_path = Path(file_path).resolve()
    allowed_dir = allowed_dir or BASE_DIR
    allowed_dir = allowed_dir.resolve()
    
    # Check if the resolved path is within the allowed directory
    try:
        file_path.relative_to(allowed_dir)
        return file_path
    except ValueError:
        # Path is outside allowed directory
        raise ValueError(f"Path {file_path} is outside allowed directory {allowed_dir}")


class Recipe:
    """Unified prompt recipe supporting quick mode (structured fields), template mode (text with variables), and hybrid mode."""
    
    def __init__(self, name: str, description: str = "", recipe_type: str = "quick",
                 template_text: str = "", variables: Dict[str, List[str]] = None,
                 last_values: Dict[str, str] = None, is_builtin: bool = False,
                 style_mode: str = "stylized", negative_prompt: str = "",
                 quick_fields: Dict[str, Any] = None):
        self.name = name
        self.description = description
        self.recipe_type = recipe_type  # "quick", "template", or "hybrid"
        self.template_text = template_text
        self.variables = variables or {}
        self.last_values = last_values or {}
        self.is_builtin = is_builtin
        self.style_mode = style_mode
        self.negative_prompt = negative_prompt
        base_quick_fields = {
            "subject": "",
            "style": "",
            "lighting": "",
            "mood": "",
            "color": "",
            "count": 5,
            "subject_lock": True,
        }
        legacy_fields = quick_fields or {}
        # Preserve legacy data but drop deprecated keys like "action"
        legacy_fields.pop("action", None)
        self.quick_fields = {**base_quick_fields, **legacy_fields}
        self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert recipe to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "recipe_type": self.recipe_type,
            "template_text": self.template_text,
            "variables": self.variables,
            "last_values": self.last_values,
            "is_builtin": self.is_builtin,
            "style_mode": self.style_mode,
            "negative_prompt": self.negative_prompt,
            "quick_fields": self.quick_fields,
            "created_at": self.created_at,
            "modified_at": self.modified_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Recipe':
        """Create recipe from dictionary."""
        recipe = cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            recipe_type=data.get("recipe_type", "quick"),
            template_text=data.get("template_text", ""),
            variables=data.get("variables", {}),
            last_values=data.get("last_values", {}),
            is_builtin=data.get("is_builtin", False),
            style_mode=data.get("style_mode", "stylized"),
            negative_prompt=data.get("negative_prompt", ""),
            quick_fields=data.get("quick_fields", {})
        )
        recipe.created_at = data.get("created_at", datetime.now().isoformat())
        recipe.modified_at = data.get("modified_at", datetime.now().isoformat())
        return recipe
    
    @classmethod
    def from_template(cls, template: 'Template') -> 'Recipe':
        """Migrate old Template to new Recipe format."""
        recipe = cls(
            name=template.name,
            description=template.description,
            recipe_type="template",
            template_text=template.template_text,
            variables=template.variables,
            last_values=template.last_values,
            is_builtin=template.is_builtin
        )
        recipe.created_at = template.created_at
        recipe.modified_at = template.modified_at
        return recipe
    
    def extract_variables(self) -> List[str]:
        """Extract variable names from template text."""
        pattern = r'\{(\w+)\}'
        variables = re.findall(pattern, self.template_text)
        return list(set(variables))  # Remove duplicates
    
    def expand(self, variable_values: Dict[str, str]) -> str:
        """Expand template with provided variable values."""
        result = self.template_text
        for var_name, value in variable_values.items():
            result = result.replace(f"{{{var_name}}}", value)
        return result
    
    def to_quick_prompt(self) -> str:
        """Generate prompt from quick fields."""
        fields = self.quick_fields
        parts = []
        
        if fields.get("mood"):
            parts.append(fields["mood"])
        if fields.get("subject"):
            parts.append(fields["subject"])
        if fields.get("style"):
            parts.append(f"in {fields['style']} style")
        if fields.get("lighting"):
            parts.append(f"with {fields['lighting']} lighting")
        if fields.get("color"):
            parts.append(f"{fields['color']} colors")
        
        return " ".join(parts) if parts else ""


class Template:
    """Represents a prompt template with variables."""
    
    def __init__(self, name: str, description: str = "", template_text: str = "", 
                 variables: Dict[str, List[str]] = None, is_builtin: bool = False,
                 last_values: Dict[str, str] = None):
        self.name = name
        self.description = description
        self.template_text = template_text
        self.variables = variables or {}
        self.is_builtin = is_builtin
        self.last_values = last_values or {}
        self.created_at = datetime.now().isoformat()
        self.modified_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """Convert template to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "template_text": self.template_text,
            "variables": self.variables,
            "is_builtin": self.is_builtin,
            "last_values": self.last_values,
            "created_at": self.created_at,
            "modified_at": self.modified_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Template':
        """Create template from dictionary."""
        template = cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            template_text=data.get("template_text", ""),
            variables=data.get("variables", {}),
            is_builtin=data.get("is_builtin", False),
            last_values=data.get("last_values", {})
        )
        template.created_at = data.get("created_at", datetime.now().isoformat())
        template.modified_at = data.get("modified_at", datetime.now().isoformat())
        return template
    
    def extract_variables(self) -> List[str]:
        """Extract variable names from template text."""
        pattern = r'\{(\w+)\}'
        variables = re.findall(pattern, self.template_text)
        return list(set(variables))  # Remove duplicates
    
    def expand(self, variable_values: Dict[str, str]) -> str:
        """Expand template with provided variable values."""
        result = self.template_text
        for var_name, value in variable_values.items():
            result = result.replace(f"{{{var_name}}}", value)
        return result


class RecipeManager:
    """Manages unified recipe library with backward compatibility for old templates."""
    
    def __init__(self):
        self.recipes: Dict[str, Recipe] = {}
        self._load_recipes()
        self._migrate_old_templates()
        self._load_builtin_recipes()
    
    def _load_recipes(self):
        """Load recipes from JSON file."""
        try:
            if RECIPES_FILE.exists():
                with open(RECIPES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for recipe_data in data.get("recipes", []):
                        recipe = Recipe.from_dict(recipe_data)
                        self.recipes[recipe.name] = recipe
        except Exception as e:
            logger.error("Error loading recipes: %s", e)
    
    def _save_recipes(self):
        """Save recipes to JSON file."""
        try:
            data = {
                "recipes": [recipe.to_dict() for recipe in self.recipes.values() 
                           if not recipe.is_builtin]
            }
            with open(RECIPES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Error saving recipes: %s", e)
    
    def _migrate_old_templates(self):
        """Migrate old templates to recipe format if recipes.json doesn't exist yet."""
        if RECIPES_FILE.exists():
            return  # Already migrated
        
        if not TEMPLATES_FILE.exists():
            return  # No old templates to migrate
        
        try:
            with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for template_data in data.get("templates", []):
                    template = Template.from_dict(template_data)
                    recipe = Recipe.from_template(template)
                    self.recipes[recipe.name] = recipe
            
            # Save migrated recipes
            self._save_recipes()
            logger.info("Migrated old templates to recipe format")
        except Exception as e:
            logger.error("Error migrating templates: %s", e)
    
    def _load_builtin_recipes(self):
        """Load built-in recipes."""
        builtin_recipes = self._get_builtin_recipes()
        for recipe in builtin_recipes:
            if recipe.name not in self.recipes:
                self.recipes[recipe.name] = recipe
    
    def _get_builtin_recipes(self) -> List[Recipe]:
        """Built-in template-variable recipes removed; Recipe Library uses Quick Build only."""
        return []

    def _get_builtin_recipes_legacy(self) -> List[Recipe]:
        """Preserved for reference only — not called from active code."""
        return [
            Recipe(
                name="Epic Fantasy Scene",
                description="A dramatic fantasy scene with customizable elements",
                recipe_type="template",
                template_text="a {mood} {subject} in a {style} fantasy setting, with {lighting} and {color} colors, showing {action}",
                variables={
                    "mood": ["epic", "playful", "mysterious", "dark", "triumphant"],
                    "subject": ["dragon", "wizard", "knight", "warrior", "castle"],
                    "style": ["oil painting", "digital art", "realistic", "surreal", "anime"],
                    "lighting": ["golden hour", "moonlight", "neon", "candlelight", "dramatic"],
                    "color": ["rich golds", "deep purples", "cool blues", "warm reds", "emerald greens"],
                    "action": ["soaring", "casting spells", "in battle", "standing guard", "exploring"]
                },
                is_builtin=True
            ),
            Recipe(
                name="Cinematic Landscape",
                description="Beautiful landscape with cinematic quality",
                recipe_type="template",
                template_text="a {mood} {landscape_type} landscape in {style} style, with {lighting} and {color} tones, {weather} weather",
                variables={
                    "mood": ["serene", "dramatic", "mysterious", "peaceful", "majestic"],
                    "landscape_type": ["mountain", "ocean", "forest", "desert", "valley"],
                    "style": ["photorealistic", "cinematic", "digital art", "oil painting", "watercolor"],
                    "lighting": ["golden hour", "blue hour", "moonlight", "sunrise", "sunset"],
                    "color": ["warm", "cool", "vibrant", "muted", "pastel"],
                    "weather": ["clear", "cloudy", "foggy", "stormy", "snowy"]
                },
                is_builtin=True
            ),
            Recipe(
                name="Portrait Close-Up",
                description="Detailed portrait with artistic styling",
                recipe_type="template",
                template_text="a {mood} {subject} portrait in {style} style, {lighting}, {color} color palette, {expression} expression",
                variables={
                    "mood": ["intense", "serene", "mysterious", "joyful", "melancholic"],
                    "subject": ["woman", "man", "child", "elderly person", "fantasy character"],
                    "style": ["photorealistic", "oil painting", "digital art", "watercolor", "sketch"],
                    "lighting": ["studio", "natural", "dramatic", "soft", "rim"],
                    "color": ["warm", "cool", "monochrome", "vibrant", "muted"],
                    "expression": ["smiling", "serious", "thoughtful", "determined", "gentle"]
                },
                is_builtin=True
            ),
            Recipe(
                name="Space Scene",
                description="Cosmic scene with celestial elements",
                recipe_type="template",
                template_text="a {mood} space scene featuring {celestial_object}, {style} style, {lighting}, {color} nebulae, {composition} composition",
                variables={
                    "mood": ["mysterious", "epic", "peaceful", "dramatic", "ethereal"],
                    "celestial_object": ["planet", "galaxy", "nebula", "star cluster", "black hole"],
                    "style": ["photorealistic", "digital art", "concept art", "surreal", "minimalist"],
                    "lighting": ["starlight", "nebula glow", "distant sun", "cosmic", "dramatic"],
                    "color": ["purple and blue", "red and orange", "cyan and white", "gold and silver", "rainbow"],
                    "composition": ["wide angle", "close-up", "panoramic", "symmetrical", "dynamic"]
                },
                is_builtin=True
            ),
            Recipe(
                name="Cyberpunk City",
                description="Futuristic cityscape with cyberpunk aesthetic",
                recipe_type="template",
                template_text="a {mood} cyberpunk city at {time_of_day}, {style} style, {lighting}, {color} neon lights, {activity} in the streets",
                variables={
                    "mood": ["dystopian", "vibrant", "mysterious", "chaotic", "elegant"],
                    "time_of_day": ["night", "dawn", "dusk", "midnight", "twilight"],
                    "style": ["digital art", "photorealistic", "concept art", "anime", "synthwave"],
                    "lighting": ["neon", "holographic", "street lights", "billboard glow", "ambient"],
                    "color": ["pink and blue", "purple and cyan", "red and green", "orange and yellow", "monochrome"],
                    "activity": ["flying cars", "crowds", "robots", "cybernetic humans", "drones"]
                },
                is_builtin=True
            ),
            Recipe(
                name="Product Shot",
                description="Professional product photography style",
                recipe_type="template",
                template_text="a {mood} {product} product shot, {style} style, {lighting}, {background} background, {angle} angle",
                variables={
                    "mood": ["professional", "elegant", "modern", "minimalist", "dramatic"],
                    "product": ["electronics", "food", "cosmetics", "fashion", "automotive"],
                    "style": ["photorealistic", "studio", "lifestyle", "minimalist", "artistic"],
                    "lighting": ["studio", "natural", "soft", "dramatic", "backlit"],
                    "background": ["white", "black", "gradient", "textured", "blurred"],
                    "angle": ["front", "45-degree", "top-down", "side", "close-up"]
                },
                is_builtin=True
            )
        ]
    
    def get_recipe(self, name: str) -> Optional[Recipe]:
        """Get recipe by name."""
        return self.recipes.get(name)
    
    def get_all_recipes(self) -> List[Recipe]:
        """Get all recipes."""
        return list(self.recipes.values())
    
    def get_builtin_recipes(self) -> List[Recipe]:
        """Get built-in recipes only."""
        return [r for r in self.recipes.values() if r.is_builtin]
    
    def get_custom_recipes(self) -> List[Recipe]:
        """Get custom recipes only."""
        return [r for r in self.recipes.values() if not r.is_builtin]
    
    def add_recipe(self, recipe: Recipe) -> bool:
        """Add a new recipe."""
        if recipe.name in self.recipes and not self.recipes[recipe.name].is_builtin:
            return False  # Custom recipe with same name exists
        
        recipe.modified_at = datetime.now().isoformat()
        self.recipes[recipe.name] = recipe
        
        if not recipe.is_builtin:
            self._save_recipes()
        
        return True
    
    def update_recipe(self, recipe: Recipe) -> bool:
        """Update an existing recipe."""
        if recipe.name not in self.recipes:
            return False
        
        if self.recipes[recipe.name].is_builtin:
            return False  # Cannot update built-in recipes
        
        recipe.modified_at = datetime.now().isoformat()
        self.recipes[recipe.name] = recipe
        self._save_recipes()
        return True
    
    def delete_recipe(self, name: str) -> bool:
        """Delete a recipe."""
        if name not in self.recipes:
            return False
        
        if self.recipes[name].is_builtin:
            return False  # Cannot delete built-in recipes
        
        del self.recipes[name]
        self._save_recipes()
        return True
    
    def export_recipe(self, name: str, export_path: Path) -> bool:
        """Export a recipe to a JSON file."""
        recipe = self.get_recipe(name)
        if not recipe:
            return False
        
        try:
            export_path = _validate_path(export_path)
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(recipe.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logger.error("Error exporting recipe: %s", e)
            return False
    
    def import_recipe(self, import_path: Path) -> bool:
        """Import a recipe from a JSON file."""
        try:
            import_path = _validate_path(import_path)
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Support both old template format and new recipe format
            if "recipe_type" in data:
                recipe = Recipe.from_dict(data)
            else:
                # Migrate old template format
                template = Template.from_dict(data)
                recipe = Recipe.from_template(template)
            
            recipe.is_builtin = False  # Imported recipes are custom
            
            # If name conflicts, add suffix
            original_name = recipe.name
            counter = 1
            while recipe.name in self.recipes:
                recipe.name = f"{original_name}_{counter}"
                counter += 1
            
            return self.add_recipe(recipe)
        except Exception as e:
            logger.error("Error importing recipe: %s", e)
            return False
    
    def search_recipes(self, query: str) -> List[Recipe]:
        """Search recipes by name or description."""
        query = query.lower()
        results = []
        for recipe in self.recipes.values():
            if query in recipe.name.lower() or query in recipe.description.lower():
                results.append(recipe)
        return results


class TemplateManager:
    """Manages template library and operations."""
    
    def __init__(self):
        self.templates: Dict[str, Template] = {}
        self._load_templates()
        self._load_builtin_templates()
    
    def _load_templates(self):
        """Load templates from JSON file."""
        try:
            if TEMPLATES_FILE.exists():
                with open(TEMPLATES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for template_data in data.get("templates", []):
                        template = Template.from_dict(template_data)
                        self.templates[template.name] = template
        except Exception as e:
            logger.error("Error loading templates: %s", e)
    
    def _save_templates(self):
        """Save templates to JSON file."""
        try:
            data = {
                "templates": [template.to_dict() for template in self.templates.values() 
                            if not template.is_builtin]
            }
            with open(TEMPLATES_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Error saving templates: %s", e)
    
    def _load_builtin_templates(self):
        """Load built-in templates."""
        builtin_templates = self._get_builtin_templates()
        for template in builtin_templates:
            if template.name not in self.templates:
                self.templates[template.name] = template
    
    def _get_builtin_templates(self) -> List[Template]:
        """Get list of built-in templates."""
        return [
            Template(
                name="Epic Fantasy Scene",
                description="A dramatic fantasy scene with customizable elements",
                template_text="a {mood} {subject} in a {style} fantasy setting, with {lighting} and {color} colors, showing {action}",
                variables={
                    "mood": ["epic", "playful", "mysterious", "dark", "triumphant"],
                    "subject": ["dragon", "wizard", "knight", "warrior", "castle"],
                    "style": ["oil painting", "digital art", "realistic", "surreal", "anime"],
                    "lighting": ["golden hour", "moonlight", "neon", "candlelight", "dramatic"],
                    "color": ["rich golds", "deep purples", "cool blues", "warm reds", "emerald greens"],
                    "action": ["soaring", "casting spells", "in battle", "standing guard", "exploring"]
                },
                is_builtin=True
            ),
            Template(
                name="Cinematic Landscape",
                description="Beautiful landscape with cinematic quality",
                template_text="a {mood} {landscape_type} landscape in {style} style, with {lighting} and {color} tones, {weather} weather",
                variables={
                    "mood": ["serene", "dramatic", "mysterious", "peaceful", "majestic"],
                    "landscape_type": ["mountain", "ocean", "forest", "desert", "valley"],
                    "style": ["photorealistic", "cinematic", "digital art", "oil painting", "watercolor"],
                    "lighting": ["golden hour", "blue hour", "moonlight", "sunrise", "sunset"],
                    "color": ["warm", "cool", "vibrant", "muted", "pastel"],
                    "weather": ["clear", "cloudy", "foggy", "stormy", "snowy"]
                },
                is_builtin=True
            ),
            Template(
                name="Portrait Close-Up",
                description="Detailed portrait with artistic styling",
                template_text="a {mood} {subject} portrait in {style} style, {lighting}, {color} color palette, {expression} expression",
                variables={
                    "mood": ["intense", "serene", "mysterious", "joyful", "melancholic"],
                    "subject": ["woman", "man", "child", "elderly person", "fantasy character"],
                    "style": ["photorealistic", "oil painting", "digital art", "watercolor", "sketch"],
                    "lighting": ["studio", "natural", "dramatic", "soft", "rim"],
                    "color": ["warm", "cool", "monochrome", "vibrant", "muted"],
                    "expression": ["smiling", "serious", "thoughtful", "determined", "gentle"]
                },
                is_builtin=True
            ),
            Template(
                name="Space Scene",
                description="Cosmic scene with celestial elements",
                template_text="a {mood} space scene featuring {celestial_object}, {style} style, {lighting}, {color} nebulae, {composition} composition",
                variables={
                    "mood": ["mysterious", "epic", "peaceful", "dramatic", "ethereal"],
                    "celestial_object": ["planet", "galaxy", "nebula", "star cluster", "black hole"],
                    "style": ["photorealistic", "digital art", "concept art", "surreal", "minimalist"],
                    "lighting": ["starlight", "nebula glow", "distant sun", "cosmic", "dramatic"],
                    "color": ["purple and blue", "red and orange", "cyan and white", "gold and silver", "rainbow"],
                    "composition": ["wide angle", "close-up", "panoramic", "symmetrical", "dynamic"]
                },
                is_builtin=True
            ),
            Template(
                name="Cyberpunk City",
                description="Futuristic cityscape with cyberpunk aesthetic",
                template_text="a {mood} cyberpunk city at {time_of_day}, {style} style, {lighting}, {color} neon lights, {activity} in the streets",
                variables={
                    "mood": ["dystopian", "vibrant", "mysterious", "chaotic", "elegant"],
                    "time_of_day": ["night", "dawn", "dusk", "midnight", "twilight"],
                    "style": ["digital art", "photorealistic", "concept art", "anime", "synthwave"],
                    "lighting": ["neon", "holographic", "street lights", "billboard glow", "ambient"],
                    "color": ["pink and blue", "purple and cyan", "red and green", "orange and yellow", "monochrome"],
                    "activity": ["flying cars", "crowds", "robots", "cybernetic humans", "drones"]
                },
                is_builtin=True
            ),
            Template(
                name="Product Shot",
                description="Professional product photography style",
                template_text="a {mood} {product} product shot, {style} style, {lighting}, {background} background, {angle} angle",
                variables={
                    "mood": ["professional", "elegant", "modern", "minimalist", "dramatic"],
                    "product": ["electronics", "food", "cosmetics", "fashion", "automotive"],
                    "style": ["photorealistic", "studio", "lifestyle", "minimalist", "artistic"],
                    "lighting": ["studio", "natural", "soft", "dramatic", "backlit"],
                    "background": ["white", "black", "gradient", "textured", "blurred"],
                    "angle": ["front", "45-degree", "top-down", "side", "close-up"]
                },
                is_builtin=True
            )
        ]
    
    def get_template(self, name: str) -> Optional[Template]:
        """Get template by name."""
        return self.templates.get(name)
    
    def get_all_templates(self) -> List[Template]:
        """Get all templates."""
        return list(self.templates.values())
    
    def get_builtin_templates(self) -> List[Template]:
        """Get built-in templates only."""
        return [t for t in self.templates.values() if t.is_builtin]
    
    def get_custom_templates(self) -> List[Template]:
        """Get custom templates only."""
        return [t for t in self.templates.values() if not t.is_builtin]
    
    def add_template(self, template: Template) -> bool:
        """Add a new template."""
        if template.name in self.templates and not self.templates[template.name].is_builtin:
            return False  # Custom template with same name exists
        
        template.modified_at = datetime.now().isoformat()
        self.templates[template.name] = template
        
        if not template.is_builtin:
            self._save_templates()
        
        return True
    
    def update_template(self, template: Template) -> bool:
        """Update an existing template."""
        if template.name not in self.templates:
            return False
        
        if self.templates[template.name].is_builtin:
            return False  # Cannot update built-in templates
        
        template.modified_at = datetime.now().isoformat()
        self.templates[template.name] = template
        self._save_templates()
        return True
    
    def delete_template(self, name: str) -> bool:
        """Delete a template."""
        if name not in self.templates:
            return False
        
        if self.templates[name].is_builtin:
            return False  # Cannot delete built-in templates
        
        del self.templates[name]
        self._save_templates()
        return True
    
    def export_template(self, name: str, export_path: Path) -> bool:
        """Export a template to a JSON file."""
        template = self.get_template(name)
        if not template:
            return False
        
        try:
            export_path = _validate_path(export_path)
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(template.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logger.error("Error exporting template: %s", e)
            return False
    
    def import_template(self, import_path: Path) -> bool:
        """Import a template from a JSON file."""
        try:
            import_path = _validate_path(import_path)
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            template = Template.from_dict(data)
            template.is_builtin = False  # Imported templates are custom
            
            # If name conflicts, add suffix
            original_name = template.name
            counter = 1
            while template.name in self.templates:
                template.name = f"{original_name}_{counter}"
                counter += 1
            
            return self.add_template(template)
        except Exception as e:
            logger.error("Error importing template: %s", e)
            return False
    
    def search_templates(self, query: str) -> List[Template]:
        """Search templates by name or description."""
        query = query.lower()
        results = []
        for template in self.templates.values():
            if query in template.name.lower() or query in template.description.lower():
                results.append(template)
        return results


# Global instances
_template_manager = None
_recipe_manager = None

def get_template_manager() -> TemplateManager:
    """Get the global template manager instance (deprecated, use get_recipe_manager)."""
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager()
    return _template_manager

def get_recipe_manager() -> RecipeManager:
    """Get the global recipe manager instance."""
    global _recipe_manager
    if _recipe_manager is None:
        _recipe_manager = RecipeManager()
    return _recipe_manager
