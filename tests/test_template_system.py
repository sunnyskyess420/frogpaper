"""Tests for the recipe/template system in template_system.py.

Covers (improvement report §5 — testing expansion):
  - _validate_path: the path-traversal security guard
  - Recipe: defaults, legacy quick_fields cleanup ("action" key drop),
    to_dict/from_dict round-trips, variable extraction/expansion,
    quick-prompt generation, migration from old Template objects
  - Template: round-trips, variable extraction/expansion
  - RecipeManager: CRUD rules (duplicates rejected, builtins protected),
    disk persistence (builtins excluded), corrupt-file resilience,
    search, export/import round-trips incl. name-conflict suffixing,
    old template-format import, templates.json -> recipes.json migration
  - TemplateManager: builtins load, builtin protection, custom persistence

ISOLATION: RECIPES_FILE / TEMPLATES_FILE / BASE_DIR are redirected into a
per-test temp directory, so your real recipes.json, templates.json and
template folders are never read or written.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import template_system as ts


class TemplateSystemTestBase(unittest.TestCase):
    """Redirect every module-level file path into a temp directory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._patch("BASE_DIR", self.tmp)
        self._patch("TEMPLATES_FILE", self.tmp / "templates.json")
        self._patch("RECIPES_FILE", self.tmp / "recipes.json")
        self.addCleanup(self._tmp.cleanup)

    def _patch(self, name, value):
        original = getattr(ts, name)
        setattr(ts, name, value)
        self.addCleanup(setattr, ts, name, original)

    def _write_json(self, path, data):
        path.write_text(json.dumps(data), encoding="utf-8")

    def _read_json(self, path):
        return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# _validate_path — the path-traversal security guard
# ---------------------------------------------------------------------------

class TestValidatePath(TemplateSystemTestBase):
    def test_path_inside_allowed_dir_accepted(self):
        out = ts._validate_path(self.tmp / "recipes.json")
        self.assertEqual(out, (self.tmp / "recipes.json").resolve())

    def test_path_outside_allowed_dir_rejected(self):
        with self.assertRaises(ValueError):
            ts._validate_path(self.tmp / ".." / "evil.json")

    def test_dotdot_segments_resolve_before_check(self):
        """sub/.. collapses back inside — must be accepted, not rejected."""
        sneaky = self.tmp / "sub" / ".." / "recipes.json"
        out = ts._validate_path(sneaky)
        self.assertEqual(out, (self.tmp / "recipes.json").resolve())


# ---------------------------------------------------------------------------
# Recipe object
# ---------------------------------------------------------------------------

class TestRecipe(TemplateSystemTestBase):
    def test_defaults(self):
        r = ts.Recipe("My Recipe")
        self.assertEqual(r.recipe_type, "quick")
        self.assertEqual(r.quick_fields["count"], 5)
        self.assertTrue(r.quick_fields["subject_lock"])
        self.assertEqual(r.style_mode, "stylized")
        self.assertFalse(r.is_builtin)

    def test_legacy_action_key_dropped(self):
        r = ts.Recipe("R", quick_fields={"action": "jumping", "count": 9})
        self.assertNotIn("action", r.quick_fields)
        self.assertEqual(r.quick_fields["count"], 9)  # legacy values kept

    def test_dict_round_trip(self):
        r = ts.Recipe(
            "Round Trip", description="desc", recipe_type="template",
            template_text="a {mood} frog", variables={"mood": ["dark"]},
            last_values={"mood": "dark"}, style_mode="surreal",
            negative_prompt="blurry",
        )
        clone = ts.Recipe.from_dict(r.to_dict())
        self.assertEqual(clone.name, r.name)
        self.assertEqual(clone.description, r.description)
        self.assertEqual(clone.recipe_type, r.recipe_type)
        self.assertEqual(clone.template_text, r.template_text)
        self.assertEqual(clone.variables, r.variables)
        self.assertEqual(clone.last_values, r.last_values)
        self.assertEqual(clone.style_mode, r.style_mode)
        self.assertEqual(clone.negative_prompt, r.negative_prompt)
        self.assertEqual(clone.created_at, r.created_at)
        self.assertEqual(clone.modified_at, r.modified_at)

    def test_extract_variables_deduplicates(self):
        r = ts.Recipe("R", recipe_type="template",
                      template_text="{mood} frog on a {mood} {subject} lily pad")
        self.assertEqual(sorted(r.extract_variables()), ["mood", "subject"])

    def test_expand_replaces_known_leaves_unknown(self):
        r = ts.Recipe("R", recipe_type="template",
                      template_text="a {mood} frog with {missing} intact")
        self.assertEqual(r.expand({"mood": "sleepy"}),
                         "a sleepy frog with {missing} intact")

    def test_to_quick_prompt_full_ordering(self):
        r = ts.Recipe("R", quick_fields={
            "mood": "epic", "subject": "dragon", "style": "oil painting",
            "lighting": "golden hour", "color": "rich golds",
        })
        self.assertEqual(
            r.to_quick_prompt(),
            "epic dragon in oil painting style with golden hour lighting "
            "rich golds colors")

    def test_to_quick_prompt_empty_fields(self):
        self.assertEqual(ts.Recipe("R").to_quick_prompt(), "")

    def test_from_template_migration(self):
        t = ts.Template("Old Template", template_text="{mood} scene",
                        variables={"mood": ["dark"]})
        t.created_at = "2020-01-01T00:00:00"
        r = ts.Recipe.from_template(t)
        self.assertEqual(r.recipe_type, "template")
        self.assertEqual(r.name, "Old Template")
        self.assertEqual(r.template_text, "{mood} scene")
        self.assertEqual(r.variables, {"mood": ["dark"]})
        self.assertEqual(r.created_at, "2020-01-01T00:00:00")


class TestTemplate(TemplateSystemTestBase):
    def test_dict_round_trip(self):
        t = ts.Template("T", description="d", template_text="{a} and {b}",
                        variables={"a": ["1"], "b": ["2"]},
                        last_values={"a": "1"}, is_builtin=True)
        clone = ts.Template.from_dict(t.to_dict())
        self.assertEqual(clone.name, t.name)
        self.assertEqual(clone.template_text, t.template_text)
        self.assertEqual(clone.variables, t.variables)
        self.assertEqual(clone.last_values, t.last_values)
        self.assertEqual(clone.is_builtin, True)
        self.assertEqual(clone.created_at, t.created_at)

    def test_extract_and_expand(self):
        t = ts.Template("T", template_text="{mood} {mood} {mood}")
        self.assertEqual(t.extract_variables(), ["mood"])
        self.assertEqual(t.expand({"mood": "dark"}), "dark dark dark")


# ---------------------------------------------------------------------------
# RecipeManager
# ---------------------------------------------------------------------------

class TestRecipeManagerCrud(TemplateSystemTestBase):
    def test_fresh_manager_starts_empty(self):
        manager = ts.RecipeManager()
        self.assertEqual(manager.get_all_recipes(), [])
        self.assertFalse(ts.RECIPES_FILE.exists())

    def test_corrupt_recipes_file_degrades_gracefully(self):
        ts.RECIPES_FILE.write_text("{definitely not json", encoding="utf-8")
        manager = ts.RecipeManager()  # must not raise
        self.assertEqual(manager.get_all_recipes(), [])

    def test_add_recipe_saves_custom_to_disk(self):
        manager = ts.RecipeManager()
        self.assertTrue(manager.add_recipe(ts.Recipe("Mine", template_text="x")))
        self.assertTrue(ts.RECIPES_FILE.exists())
        data = self._read_json(ts.RECIPES_FILE)
        self.assertEqual(data["recipes"][0]["name"], "Mine")
        self.assertIsNotNone(manager.get_recipe("Mine"))

    def test_add_recipe_rejects_duplicate_custom_name(self):
        manager = ts.RecipeManager()
        manager.add_recipe(ts.Recipe("Mine"))
        self.assertFalse(manager.add_recipe(ts.Recipe("Mine")))

    def test_update_recipe_persists_changes(self):
        manager = ts.RecipeManager()
        manager.add_recipe(ts.Recipe("Mine", description="before"))
        updated = ts.Recipe("Mine", description="after")
        self.assertTrue(manager.update_recipe(updated))
        reloaded = ts.RecipeManager()
        self.assertEqual(reloaded.get_recipe("Mine").description, "after")

    def test_update_missing_recipe_fails(self):
        self.assertFalse(ts.RecipeManager().update_recipe(ts.Recipe("Ghost")))

    def test_delete_recipe_removes_from_disk(self):
        manager = ts.RecipeManager()
        manager.add_recipe(ts.Recipe("Mine"))
        self.assertTrue(manager.delete_recipe("Mine"))
        self.assertIsNone(manager.get_recipe("Mine"))
        reloaded = ts.RecipeManager()
        self.assertIsNone(reloaded.get_recipe("Mine"))
        self.assertFalse(manager.delete_recipe("Mine"))  # second delete fails

    def test_builtin_recipes_cannot_be_updated_or_deleted(self):
        manager = ts.RecipeManager()
        manager.recipes["Builtin"] = ts.Recipe("Builtin", is_builtin=True)
        self.assertFalse(manager.update_recipe(ts.Recipe("Builtin", description="x")))
        self.assertFalse(manager.delete_recipe("Builtin"))
        self.assertIn("Builtin", manager.recipes)

    def test_builtin_recipes_excluded_from_disk_saves(self):
        manager = ts.RecipeManager()
        manager.recipes["Builtin"] = ts.Recipe("Builtin", is_builtin=True)
        manager.add_recipe(ts.Recipe("Mine"))
        names = [r["name"] for r in self._read_json(ts.RECIPES_FILE)["recipes"]]
        self.assertEqual(names, ["Mine"])

    def test_persistence_round_trip(self):
        manager = ts.RecipeManager()
        manager.add_recipe(ts.Recipe(
            "Mine", recipe_type="template", template_text="a {mood} frog",
            variables={"mood": ["dark"]}))
        reloaded = ts.RecipeManager()
        recipe = reloaded.get_recipe("Mine")
        self.assertEqual(recipe.template_text, "a {mood} frog")
        self.assertEqual(recipe.variables, {"mood": ["dark"]})
        self.assertFalse(recipe.is_builtin)


class TestRecipeManagerSearch(TemplateSystemTestBase):
    def test_search_matches_name_or_description_case_insensitive(self):
        manager = ts.RecipeManager()
        manager.add_recipe(ts.Recipe("Sunset Vista", description="warm beach"))
        manager.add_recipe(ts.Recipe("Night City", description="neon streets"))
        self.assertEqual(len(manager.search_recipes("SUNSET")), 1)
        self.assertEqual(len(manager.search_recipes("beach")), 1)
        self.assertEqual(len(manager.search_recipes("neon")), 1)
        self.assertEqual(manager.search_recipes("castle"), [])


class TestRecipeManagerExportImport(TemplateSystemTestBase):
    def test_export_then_import_round_trip(self):
        manager = ts.RecipeManager()
        manager.add_recipe(ts.Recipe("Mine", template_text="x"))
        export_path = self.tmp / "shared.json"
        self.assertTrue(manager.export_recipe("Mine", export_path))
        self.assertTrue(manager.delete_recipe("Mine"))
        self.assertTrue(manager.import_recipe(export_path))
        self.assertIsNotNone(manager.get_recipe("Mine"))

    def test_export_missing_recipe_fails(self):
        self.assertFalse(
            ts.RecipeManager().export_recipe("Ghost", self.tmp / "g.json"))

    def test_import_missing_file_fails(self):
        self.assertFalse(
            ts.RecipeManager().import_recipe(self.tmp / "nope.json"))

    def test_import_name_conflict_gets_suffix(self):
        manager = ts.RecipeManager()
        manager.add_recipe(ts.Recipe("Mine", template_text="v1"))
        export_path = self.tmp / "shared.json"
        manager.export_recipe("Mine", export_path)
        self.assertTrue(manager.import_recipe(export_path))
        self.assertIsNotNone(manager.get_recipe("Mine_1"))
        self.assertEqual(manager.get_recipe("Mine_1").template_text, "v1")

    def test_import_old_template_format_becomes_recipe(self):
        old_format = {
            "name": "Legacy", "description": "old style",
            "template_text": "{mood} scene", "variables": {"mood": ["dark"]},
            "is_builtin": False, "last_values": {},
        }
        path = self.tmp / "legacy.json"
        self._write_json(path, old_format)
        manager = ts.RecipeManager()
        self.assertTrue(manager.import_recipe(path))
        recipe = manager.get_recipe("Legacy")
        self.assertEqual(recipe.recipe_type, "template")
        self.assertEqual(recipe.template_text, "{mood} scene")


class TestRecipeMigration(TemplateSystemTestBase):
    def test_old_templates_migrate_to_recipes(self):
        self._write_json(ts.TEMPLATES_FILE, {"templates": [{
            "name": "Legacy Template", "description": "old",
            "template_text": "{mood} scene", "variables": {"mood": ["dark"]},
            "is_builtin": False, "last_values": {},
        }]})
        manager = ts.RecipeManager()
        recipe = manager.get_recipe("Legacy Template")
        self.assertIsNotNone(recipe)
        self.assertEqual(recipe.recipe_type, "template")
        # migration wrote the recipes file for future loads
        self.assertTrue(ts.RECIPES_FILE.exists())

    def test_migration_skipped_when_recipes_file_exists(self):
        self._write_json(ts.RECIPES_FILE, {"recipes": [
            ts.Recipe("Already There").to_dict()]})
        self._write_json(ts.TEMPLATES_FILE, {"templates": [{
            "name": "Should Not Migrate", "template_text": "x",
        }]})
        manager = ts.RecipeManager()
        self.assertIsNotNone(manager.get_recipe("Already There"))
        self.assertIsNone(manager.get_recipe("Should Not Migrate"))


# ---------------------------------------------------------------------------
# TemplateManager
# ---------------------------------------------------------------------------

class TestTemplateManager(TemplateSystemTestBase):
    def test_builtin_templates_loaded(self):
        manager = ts.TemplateManager()
        builtins = manager.get_builtin_templates()
        self.assertEqual(len(builtins), 6)
        names = {t.name for t in builtins}
        self.assertIn("Epic Fantasy Scene", names)
        self.assertIn("Cyberpunk City", names)

    def test_builtin_templates_cannot_be_deleted_or_updated(self):
        manager = ts.TemplateManager()
        self.assertFalse(manager.delete_template("Epic Fantasy Scene"))
        cloned = ts.Template.from_dict(
            manager.get_template("Epic Fantasy Scene").to_dict())
        self.assertFalse(manager.update_template(cloned))

    def test_custom_template_persists_and_reloads(self):
        manager = ts.TemplateManager()
        self.assertTrue(manager.add_template(
            ts.Template("Custom One", template_text="{mood} wall")))
        self.assertFalse(manager.add_template(
            ts.Template("Custom One", template_text="dup")))
        reloaded = ts.TemplateManager()
        self.assertEqual(reloaded.get_template("Custom One").template_text,
                         "{mood} wall")
        # builtins still present alongside the custom one
        self.assertIsNotNone(reloaded.get_template("Space Scene"))

    def test_search_templates(self):
        manager = ts.TemplateManager()
        self.assertTrue(manager.search_templates("cyberpunk"))
        self.assertTrue(manager.search_templates("PORTRAIT"))
        self.assertEqual(manager.search_templates("quantum flux"), [])

    def test_import_template_conflict_suffix(self):
        manager = ts.TemplateManager()
        path = self.tmp / "custom.json"
        self._write_json(path, {
            "name": "Custom One", "template_text": "{mood} wall",
        })
        self.assertTrue(manager.import_template(path))
        self.assertTrue(manager.import_template(path))
        self.assertIsNotNone(manager.get_template("Custom One"))
        self.assertIsNotNone(manager.get_template("Custom One_1"))


# ---------------------------------------------------------------------------
# Singleton accessors
# ---------------------------------------------------------------------------

class TestSingletons(TemplateSystemTestBase):
    def test_accessors_return_same_instance(self):
        self.assertIs(ts.get_recipe_manager(), ts.get_recipe_manager())
        self.assertIs(ts.get_template_manager(), ts.get_template_manager())


if __name__ == "__main__":
    unittest.main()
