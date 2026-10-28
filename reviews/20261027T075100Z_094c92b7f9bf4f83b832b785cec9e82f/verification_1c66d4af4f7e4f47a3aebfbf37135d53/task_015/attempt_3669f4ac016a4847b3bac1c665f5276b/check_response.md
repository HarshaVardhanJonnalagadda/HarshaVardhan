## Assessment  
**REFUTED IN THIS BATCH**

## Source evidence  
- `Database.one` implementation returns the result of `fetchone()` which yields `None` when no rows match:  
  `0348: def one(self, sql: str, parameters: tuple = ()) -> sqlite3.Row | None:`  
  `0349:     return self.execute(sql, parameters).fetchone()`  

- `seed_demo` checks the result of that call in a conditional:  
  `0837: if db.one("SELECT value FROM metadata WHERE key = 'seeded'"):`  
  `0838:     return {"seeded": False, "message": "Demo data already exists"}`  

## Explanation and limits  
`db.one` does **not** raise an exception when the `metadata` table exists but contains no rows; it simply returns `None`. The `if` statement in `seed_demo` treats a falsy result (`None`) as “not seeded” and proceeds to insert demo data. Therefore the claim that `seed_demo` may raise an exception when the `metadata` table is empty is unsupported by the provided code.  

The only way an exception could arise here is if the `metadata` table itself were missing or the `execute` method raised, neither of which is indicated in the shown source. Consequently, within this batch the claim is refuted.