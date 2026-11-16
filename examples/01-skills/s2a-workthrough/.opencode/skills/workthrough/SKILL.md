---
name: workthrough
description: Document development work and code modifications in a structured workthrough format. Use this skill when the user asks for a work record, or right after completing a development task, bug fix, feature implementation, or code refactoring, to create comprehensive documentation. 작업 기록 문서를 남길 때 사용한다: 사용자가 "workthrough로 기록해줘", "작업 내용 문서화해줘", "변경 작업 정리해줘", "작업 기록 남겨줘", "이 변경 기록해줘" 처럼 요청하거나, 기능 구현·버그 수정·리팩터링을 끝낸 직후.
license: MIT
---

This skill generates detailed workthrough documentation for development work, capturing the context, changes made, and verification results in a clear, structured format.

## When to Use This Skill

Use this skill when the user asks for a work record, or right after:
- Implementing new features or functionality
- Fixing bugs or errors
- Refactoring code
- Making configuration changes
- Updating dependencies
- Resolving build/compilation issues
- Any significant code modifications

## Documentation Structure

The workthrough documentation follows this structure:

1. **Title**: Clear, descriptive title of the work completed
2. **Overview**: Brief summary of what was accomplished and why
3. **Changes Made**: Detailed breakdown of all modifications
4. **Code Examples**: Key code snippets showing important changes
5. **Verification Results**: Build/test results confirming success

## Implementation Guidelines

When generating workthrough documentation:

### 1. Capture Complete Context
- What problem was being solved?
- What errors or issues existed before?
- What approach was taken?
- Why were specific decisions made?

### 2. Document All Changes Systematically
- List each file modified with full paths
- Describe what changed in each file
- Include before/after code snippets for significant changes
- Note any dependencies added or removed
- Document configuration updates

### 3. Show Code Examples
Use clear, well-formatted code blocks:
```language
// file: src/path/to/file.tsx
<div className="example">
  {/* Show relevant code changes */}
</div>
```

### 4. Include Verification
- Build output showing success
- Test results
- Error messages (if any remain)
- Exit codes
- Screenshots (if relevant)

### 5. Use Clear Formatting
- Use markdown headers (##, ###)
- Use bullet points and numbered lists
- Use code blocks with syntax highlighting
- Use blockquotes for output/logs
- Keep paragraphs concise

## Document Organization

Save workthrough documents with this naming convention:
```
workthrough/YYYY-MM-DD-brief-description.md
```

Or organize by feature/project:
```
workthrough/feature-name/implementation.md
workthrough/bugfix/issue-123.md
```

## Supporting Files

This skill keeps the long reference material in separate files. Read them only when the condition below is met; do not read them otherwise.

- `TEMPLATE.md` (same folder as this file): the full blank template. **Read it right before you write the document**, then follow its section order.
- `EXAMPLES.md` (same folder as this file): three complete sample documents (bug fix, feature, refactoring). Read it **only if** the user asks for an example, or you cannot decide how detailed a section should be.

## Automation Instructions

After completing ANY development work:

1. **Gather Information**
   - Review all files modified during the session
   - Collect build/test output
   - Identify the main objective that was accomplished

2. **Create Document**
   - Generate workthrough document in `workthrough/` directory
   - Use timestamp or descriptive filename
   - Follow the structure guidelines above

3. **Be Comprehensive**
   - Include all relevant details
   - Don't assume future readers have context
   - Document decisions and reasoning
   - Show concrete examples

4. **Verify Completeness**
   - Confirm all changes are documented
   - Include verification results
   - Add any relevant warnings or notes

## Quality Standards

Good workthrough documentation should:
- Be readable by other developers
- Provide enough detail to understand changes
- Include verification that changes work
- Serve as a reference for similar future work
- Capture important decisions and context

Avoid:
- Overly verbose descriptions
- Unnecessary technical jargon
- Missing verification steps
- Vague or unclear explanations
- Incomplete code examples

## Output Location

Unless specified otherwise, save workthrough documents to:
```
workthrough/YYYY-MM-DD-brief-description.md
```

Create the `workthrough/` directory if it doesn't exist.

## Integration with Workflow

Load this skill when the user asks for a record of the work, or right after you finish a development task they asked for. The documentation serves as:
- A development log/journal
- Knowledge base for the project
- Onboarding material for new developers
- Reference for debugging similar issues
- Record of architectural decisions

Remember: Good documentation is a gift to your future self and your team.
