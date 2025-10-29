# Claude Code Instructions

## Commit Guidelines

### When to Commit
- Only commit when a feature is **completed and working**
- Only commit when the user asks, or when a feature is truly done
- Do NOT commit after every small change or prompt

### Good Commit Examples
- "Add view switcher with three modes (Icons, Compact, Tree)" - one commit for entire feature
- "Improve edit page UX and dark mode support" - groups related improvements together
- "Fix button sizing and alignment issues" - bundles all related button fixes

### Bad Commit Examples (Don't do this!)
- Committing every tiny CSS tweak separately
- Multiple commits trying different approaches to fix the same bug
- Separate commits for "fix icons", "fix icons again", "nuclear fix for icons"

### Commit Message Format
Use the existing format with emoji and co-author:
```
Brief descriptive title

- Bullet point of what changed
- Another bullet point

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

## Testing Before Committing
1. Work on the feature/fix until it's complete
2. Test that it actually works
3. Fix any issues
4. THEN make ONE logical commit with clear description

## General Guidelines
- Group related changes into logical commits
- Make commit history useful and readable
- Think: "Would this commit message make sense in a changelog?"
