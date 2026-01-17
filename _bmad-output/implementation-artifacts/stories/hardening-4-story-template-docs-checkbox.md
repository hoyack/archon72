# Story HARDENING-4: Story Template Docs Checkbox

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **product owner**,
I want **a "docs updated" checkbox in story completion criteria**,
So that **documentation stays in sync with code changes**.

## Acceptance Criteria

1. **AC1: Template Updated**
   - **Given** the story template file
   - **When** reviewed
   - **Then** includes a "Documentation" section with checkbox

2. **AC2: Checkbox Placement**
   - **Given** the story template
   - **When** the docs checkbox is added
   - **Then** it appears after "Tasks / Subtasks" and before "Dev Notes"

3. **AC3: Clear Guidance**
   - **Given** the docs checkbox section
   - **When** a developer reads it
   - **Then** instructions explain what documentation should be updated

4. **AC4: Default State Unchecked**
   - **Given** a newly created story
   - **When** generated from template
   - **Then** the docs checkbox is unchecked `[ ]`

5. **AC5: Definition of Done Updated**
   - **Given** the project's definition of done
   - **When** reviewed
   - **Then** includes "documentation reflects the change"

6. **AC6: Existing Stories Unaffected**
   - **Given** existing story files
   - **When** the template changes
   - **Then** existing stories are not modified (template change is forward-looking)

## Tasks / Subtasks

- [x] Task 1: Update story template (AC: 1, 2, 4)
  - [x] Edit `_bmad/bmm/workflows/4-implementation/create-story/template.md`
  - [x] Add "## Documentation Checklist" section
  - [x] Add unchecked checkbox with guidance text

- [x] Task 2: Add documentation guidance (AC: 3)
  - [x] List common documentation that may need updates:
    - Architecture docs
    - API documentation
    - README updates
    - Inline code comments
  - [x] Explain "N/A if no public API or behavior change"

- [x] Task 3: Document definition of done change (AC: 5)
  - [x] Update project README.md with Definition of Done section
  - [x] Add "Story not done until documentation reflects the change"

- [x] Task 4: Communicate to team (AC: 5)
  - [x] Note in sprint status (this story completion)
  - [x] Documentation visible in README.md for all developers

## Dev Notes

- **Source:** Gov Epic 8 Retrospective Action Item #4 (2026-01-15)
- **Owner:** Alice (Product Owner)
- **Priority:** Low (should complete before next story creation)

### Technical Context

The retrospective identified documentation lag:

> **Documentation Lag**
> - Code outpaced documentation
> - Required reading source to understand flows
> - Architecture docs didn't keep up with velocity

The fix is process-level: add a checkbox to remind developers.

### Template Change

Current template ends with:
```markdown
## Dev Notes

- Relevant architecture patterns and constraints
...
```

New template will have:
```markdown
## Documentation Checklist

- [ ] Architecture docs updated (if patterns/structure changed)
- [ ] API docs updated (if endpoints/contracts changed)
- [ ] README updated (if setup/usage changed)
- [ ] Inline comments added for complex logic
- [ ] N/A - no documentation impact

## Dev Notes
...
```

### Team Agreement (from retrospective)

> Story not "done" until documentation reflects the change

### Project Structure Notes

- Template: `_bmad/bmm/workflows/4-implementation/create-story/template.md`
- No code changes required - template/process only

### References

- [Source: _bmad-output/implementation-artifacts/retrospectives/gov-epic-8-retro-2026-01-15.md#Action Items]
- [Source: _bmad-output/implementation-artifacts/retrospectives/gov-epic-8-retro-2026-01-15.md#Challenge Themes]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None - this was a template/process change with no code implementation.

### Completion Notes List

1. **Story Template Updated** - Added "Documentation Checklist" section to `_bmad/bmm/workflows/4-implementation/create-story/template.md`:
   - Placed between "Tasks / Subtasks" and "Dev Notes" per AC2
   - Contains unchecked checkboxes per AC4
   - Includes guidance comment per AC3
   - Five checkbox options covering common documentation types

2. **Definition of Done Added to README** - Added new "Definition of Done" subsection under "Development" in `README.md`:
   - Lists 4 completion criteria (AC pass, tests, review, docs)
   - Includes documentation checklist matching the template
   - Quotes team agreement from Gov Epic 8 Retrospective

3. **AC6 Satisfied** - Existing story files are NOT modified by this change. The template change is forward-looking and only affects newly created stories.

4. **Team Communication** - The Definition of Done is now visible in the project README.md, which is the primary documentation entry point for all developers.

### File List

**Modified:**
- `_bmad/bmm/workflows/4-implementation/create-story/template.md` - Added Documentation Checklist section
- `README.md` - Added Definition of Done subsection under Development
