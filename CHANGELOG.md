# Changelog

All notable changes to the AYON Review Submitter addon will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2024-12-20

### Added
- **Initial public release** of AYON Review Submitter addon
- **OpenRV Stack Handler**: Automatic stack/layout creation for version comparison
- **Smart Version Comparison**: Auto-compares current version with last reviewed version from same product
- **Review Submission Dialog**: Qt dialog with reviewer selection, submission type (WIP/FINAL/PACKAGE), priority flag, and comments
- **Automated Publish Workflow**: Programmatic publisher trigger with post-publish review dialog
- **Activity Comment System**: Creates AYON activity comments with user tagging (`[user](user:username)`) and high-priority markers (🔥)
- **Thumbnail Generation**: Automatic first-frame extraction from RV and upload to AYON version
- **Task Data Storage**: Stores submission metadata in task data including loaded products, reviewer, submitter, and timestamp
- **Product Tracking**: Intelligent tracking of loaded products in RV using metadata stored on source nodes
- **Loader Integration**: Custom loader plugin "Create RV Review Stack" for supported product types
- **Image Sequence Support**: Automatic detection and frame range formatting (e.g., `file.1001-1100#.exr`)
- **Multi-Context Loading**: Support for loading multiple versions simultaneously
- **Server Settings**: Fully configurable product filters, task settings, and submission options

### Features

#### Auto-Comparison Logic
- Compares versions only for configurable product types (default: render/prerender/plate)
- Uses `product_id` as key to track version history across submissions
- Automatically loads previous version when same product is loaded again
- Displays comparison message in console

#### RV Integration
- Creates stacks for side-by-side comparison
- Creates layouts for multi-view comparison
- Stores version metadata (`version_id`, `representation_id`, `file_path`) on RV source nodes
- Reads metadata from "RVSource" node type
- Supports both single and batch loading

#### Review Workflow
```
Loader → Create RV Stack → Auto-compare → Publish → Review Dialog → Activity + Thumbnail + Task Data
```

#### Configurable Settings (Server)
- **Product Type Filters**:
  - First submission filters (default: `["plate"]`)
  - Review target product types (default: `["render"]`)
  - Auto-compare product types (default: `["render", "prerender", "plate"]`)
- **Task Settings**:
  - Input linked task names (default: `["Ingest"]`)
- **Submission Settings**:
  - Auto-submit on publish (default: `false`)
  - Default reviewers list
  - Require comment (default: `true`)
  - Submission types (default: `["WIP", "FINAL", "PACKAGE"]`)

#### Data Structure
```python
submission_data = {
    "submission_type": "WIP|FINAL|PACKAGE",
    "reviewer_name": "username",
    "submitter_name": "username",
    "workfile_version_id": "uuid",
    "submitted_at": "YYYY-MM-DD HH:MM:SS",
    "loaded_products": {
        "product_id": {
            "version_id": "uuid",
            "version_name": "v001",
            "product_name": "renderMain",
            "product_type": "render"
        }
    }
}
```

### Technical Details
- **Dependencies**: AYON Core, AYON API, OpenRV, Qt (PySide/PyQt)
- **Python Version**: 3.7+
- **License**: Apache 2.0
- **Addon Type**: Client-side with server settings

### Known Limitations
- Requires OpenRV to be installed and accessible
- Limited to configured product types for auto-comparison
- No pagination for large product lists
- Thumbnail extraction requires RV session to be active

### Documentation
- Comprehensive README with installation, usage, and API reference
- Server settings schema with descriptions
- Inline code documentation

---

## Future Roadmap

### Planned for 0.1.0
- Configurable comparison rules per project

---

[0.0.1]: https://github.com/YOUR_USERNAME/ayon-review-submitter/releases/tag/v0.0.1
