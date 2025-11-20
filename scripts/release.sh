#!/bin/bash
# Interactive release script for aipartnerupflow
# Usage: ./scripts/release.sh [version]
# Example: ./scripts/release.sh 0.1.0

# Note: set -e is disabled to allow step-by-step execution
# Individual steps will handle their own error handling

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get version from argument or pyproject.toml
if [ -z "$1" ]; then
    VERSION=$(grep -E '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
    if [ -z "$VERSION" ]; then
        echo -e "${RED}Error: Could not determine version from pyproject.toml${NC}"
        exit 1
    fi
else
    VERSION="$1"
fi

TAG="v${VERSION}"
PROJECT_NAME="aipartnerupflow"

echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  aipartnerupflow Release Script v${VERSION}              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to check if step is already done
check_tag_exists() {
    if git rev-parse "${TAG}" >/dev/null 2>&1; then
        if git ls-remote --tags origin | grep -q "refs/tags/${TAG}$"; then
            return 0  # Tag exists on remote
        fi
    fi
    return 1  # Tag doesn't exist
}

check_pypi_uploaded() {
    # Check if version exists on PyPI (simple check via pip)
    pip index versions "${PROJECT_NAME}" 2>/dev/null | grep -q "${VERSION}" && return 0 || return 1
}

check_release_exists() {
    # Check if GitHub release exists using GitHub CLI
    if command -v gh &> /dev/null; then
        gh release view "${TAG}" &>/dev/null && return 0 || return 1
    fi
    return 1  # If gh not available, assume release doesn't exist
}

# Function to ask yes/no with default
ask_yn() {
    local prompt="$1"
    local default="$2"
    local answer
    
    if [ "$default" = "y" ]; then
        prompt="${prompt} [Y/n]"
    else
        prompt="${prompt} [y/N]"
    fi
    
    read -p "$(echo -e "${YELLOW}${prompt}${NC}") " answer
    answer=${answer:-$default}
    [[ $answer =~ ^[Yy]$ ]]
}

# Function to ask for menu selection
# Note: Menu display goes to stderr/stdout, only selection is returned
ask_menu() {
    local prompt="$1"
    local options="$2"
    local default="$3"
    local answer
    local line
    
    # Display menu to terminal (not captured)
    echo -e "${CYAN}${prompt}${NC}" >&2
    # Display options directly (options already have numbers/keys)
    while IFS= read -r line; do
        [ -n "$line" ] && echo -e "  ${CYAN}${line}${NC}" >&2
    done <<< "$options"
    echo "" >&2
    if [ -n "$default" ]; then
        read -p "$(echo -e "${YELLOW}Select option [${default}]:${NC} ")" answer
        answer=${answer:-$default}
    else
        read -p "$(echo -e "${YELLOW}Select option:${NC} ")" answer
    fi
    # Only return the selection (not the menu display)
    echo "$answer"
}

# Function to show main menu with all steps
# Returns selection via global variable MENU_SELECTION
show_main_menu() {
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  Release Steps Selection                                  ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    # Display menu options directly
    echo -e "${CYAN}Select a step to execute:${NC}"
    echo -e "  ${CYAN}all) Execute all steps (with interactive prompts)${NC}"
    echo -e "  ${CYAN}1) Step 1: Version Verification${NC}"
    echo -e "  ${CYAN}2) Step 2: Check Current Status${NC}"
    echo -e "  ${CYAN}3) Step 3: Clean Build Files${NC}"
    echo -e "  ${CYAN}4) Step 4: Build Package${NC}"
    echo -e "  ${CYAN}5) Step 5: Check Package${NC}"
    echo -e "  ${CYAN}6) Step 6: Git Tag${NC}"
    echo -e "  ${CYAN}7) Step 6.5: Create GitHub Release${NC}"
    echo -e "  ${CYAN}8) Step 7: Upload to PyPI${NC}"
    echo -e "  ${CYAN}9) Show Summary${NC}"
    echo -e "  ${CYAN}0) Exit${NC}"
    echo ""
    
    # Read user input directly (not captured)
    read -p "$(echo -e "${YELLOW}Select option [all]:${NC} ") " MENU_SELECTION
    MENU_SELECTION=${MENU_SELECTION:-all}
}

# Step functions
step1_version_verification() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Step 1: Version Verification${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    PYPROJECT_VERSION=$(grep -E '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
    INIT_VERSION=$(grep -E '^__version__ = ' src/${PROJECT_NAME}/__init__.py | sed 's/__version__ = "\(.*\)"/\1/')
    
    echo -e "  pyproject.toml:    ${CYAN}${PYPROJECT_VERSION}${NC}"
    echo -e "  __init__.py:       ${CYAN}${INIT_VERSION}${NC}"
    echo -e "  Script version:    ${CYAN}${VERSION}${NC}"
    
    if [ "$PYPROJECT_VERSION" != "$VERSION" ] || [ "$INIT_VERSION" != "$VERSION" ]; then
        echo -e "${RED}❌ Version mismatch detected!${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ All versions match${NC}"
    echo ""
    return 0
}

step2_check_status() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Step 2: Checking Current Status${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    STATUS_TAG="❌"
    STATUS_BUILD="❌"
    STATUS_PYPI="❌"
    
    # Check Git tag
    if check_tag_exists; then
        STATUS_TAG="${GREEN}✅${NC}"
        echo -e "  Git Tag:          ${STATUS_TAG} Tag ${TAG} exists on remote"
    else
        echo -e "  Git Tag:          ${STATUS_TAG} Tag ${TAG} not found on remote"
    fi
    
    # Check build files
    if [ -d "dist" ] && [ "$(ls -A dist/*.whl dist/*.tar.gz 2>/dev/null | wc -l)" -gt 0 ]; then
        STATUS_BUILD="${GREEN}✅${NC}"
        echo -e "  Build Files:      ${STATUS_BUILD} Found in dist/"
        ls -lh dist/ | tail -n +2 | sed 's/^/    /'
    else
        echo -e "  Build Files:      ${STATUS_BUILD} Not found"
    fi
    
    # Check PyPI (optional, may fail if not installed)
    if command -v pip &> /dev/null; then
        if pip index versions "${PROJECT_NAME}" 2>/dev/null | grep -q "${VERSION}"; then
            STATUS_PYPI="${GREEN}✅${NC}"
            echo -e "  PyPI Upload:      ${STATUS_PYPI} Version ${VERSION} found on PyPI"
        else
            echo -e "  PyPI Upload:      ${STATUS_PYPI} Version ${VERSION} not found on PyPI"
        fi
    else
        echo -e "  PyPI Upload:      ${STATUS_PYPI} (cannot check - pip not available)"
    fi
    
    echo ""
    return 0
}

step3_clean_build() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Step 3: Clean Build Files${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if [ -d "dist" ] || [ -d "build" ]; then
        echo -e "${YELLOW}Found existing build files${NC}"
        if ask_yn "Clean build files? (dist/, build/, *.egg-info/)" "y"; then
            rm -rf dist/ build/ *.egg-info/ .eggs/
            echo -e "${GREEN}✅ Cleaned${NC}"
        else
            echo -e "${YELLOW}⚠️  Skipped cleaning${NC}"
        fi
    else
        echo -e "${GREEN}✅ No build files to clean${NC}"
    fi
    echo ""
    return 0
}

step4_build_package() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Step 4: Build Package${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if [ -d "dist" ] && [ "$(ls -A dist/*.whl dist/*.tar.gz 2>/dev/null | wc -l)" -gt 0 ]; then
        echo -e "${GREEN}✅ Build files already exist${NC}"
        if ask_yn "Rebuild package?" "n"; then
            SKIP_BUILD=false
        else
            SKIP_BUILD=true
        fi
    else
        SKIP_BUILD=false
    fi
    
    if [ "$SKIP_BUILD" = false ]; then
        if ! command -v python &> /dev/null; then
            echo -e "${RED}❌ Error: python command not found${NC}"
            return 1
        fi
        
        echo -e "${YELLOW}Building package...${NC}"
        if ! python -m build; then
            echo -e "${RED}❌ Build failed${NC}"
            return 1
        fi
        echo -e "${GREEN}✅ Package built successfully${NC}"
        
        echo ""
        echo -e "${CYAN}Built files:${NC}"
        ls -lh dist/ | tail -n +2 | sed 's/^/  /'
    else
        echo -e "${YELLOW}⚠️  Skipped build (using existing files)${NC}"
    fi
    echo ""
    return 0
}

step5_check_package() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Step 5: Check Package${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if ! command -v twine &> /dev/null; then
        echo -e "${YELLOW}⚠️  twine not found, skipping check${NC}"
        echo -e "${YELLOW}   Install with: pip install twine${NC}"
    else
        if ask_yn "Check package with twine?" "y"; then
            if ! twine check dist/*; then
                echo -e "${RED}❌ Package check failed${NC}"
                return 1
            fi
            echo -e "${GREEN}✅ Package check passed${NC}"
        else
            echo -e "${YELLOW}⚠️  Skipped package check${NC}"
        fi
    fi
    echo ""
    return 0
}

step6_git_tag() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Step 6: Git Tag${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if check_tag_exists; then
        echo -e "${GREEN}✅ Tag ${TAG} already exists on remote${NC}"
        echo -e "${CYAN}   GitHub Release should be available${NC}"
        if ask_yn "Create/update tag anyway?" "n"; then
            SKIP_TAG=false
        else
            SKIP_TAG=true
        fi
    else
        SKIP_TAG=false
        if git rev-parse "${TAG}" >/dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Tag ${TAG} exists locally but not on remote${NC}"
            if ask_yn "Push existing tag to remote?" "y"; then
                git push origin "${TAG}"
                echo -e "${GREEN}✅ Tag pushed${NC}"
                SKIP_TAG=true
            fi
        fi
    fi
    
    if [ "$SKIP_TAG" = false ]; then
        if ask_yn "Create Git tag ${TAG}?" "y"; then
            # Check for uncommitted changes
            if ! git diff-index --quiet HEAD --; then
                echo -e "${YELLOW}⚠️  Warning: You have uncommitted changes${NC}"
                git status --short
                if ! ask_yn "Continue anyway?" "n"; then
                    return 1
                fi
            fi
            
            git tag -a "${TAG}" -m "Release version ${VERSION}"
            echo -e "${GREEN}✅ Tag created${NC}"
            
            if ask_yn "Push tag to remote?" "y"; then
                git push origin "${TAG}"
                echo -e "${GREEN}✅ Tag pushed to remote${NC}"
            else
                echo -e "${YELLOW}⚠️  Tag not pushed. Push manually with: git push origin ${TAG}${NC}"
            fi
        else
            echo -e "${YELLOW}⚠️  Skipped tag creation${NC}"
        fi
    fi
    echo ""
    return 0
}

step6_5_create_github_release() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Step 6.5: Create GitHub Release${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    # Check if GitHub CLI is available
    if command -v gh &> /dev/null; then
        # Verify GitHub CLI authentication
        if ! gh auth status &>/dev/null; then
            echo -e "${YELLOW}⚠️  GitHub CLI not authenticated${NC}"
            echo -e "${CYAN}   Please run: gh auth login${NC}"
            echo -e "${CYAN}   This will open a browser for authentication${NC}"
            if ask_yn "Continue anyway? (Release creation will fail)" "n"; then
                SKIP_RELEASE=false
            else
                SKIP_RELEASE=true
            fi
        else
            SKIP_RELEASE=false
        fi
        
        if [ "$SKIP_RELEASE" = false ]; then
            # Check if release already exists
            if check_release_exists; then
                echo -e "${GREEN}✅ Release ${TAG} already exists${NC}"
                if ask_yn "Update existing release?" "n"; then
                    SKIP_RELEASE=false
                else
                    SKIP_RELEASE=true
                fi
            else
                SKIP_RELEASE=false
            fi
        fi
        
        if [ "$SKIP_RELEASE" = false ]; then
        if ask_yn "Create GitHub Release ${TAG}?" "y"; then
            # Extract release notes from CHANGELOG.md
            RELEASE_NOTES=""
            if [ -f "CHANGELOG.md" ]; then
                # Extract the section for this version
                # Pattern: ## [VERSION] - DATE ... until next ## or end of file
                RELEASE_NOTES=$(awk "
                    /^## \[${VERSION}\]/ {found=1; next}
                    found && /^## \[/ {exit}
                    found {print}
                " CHANGELOG.md)
                
                # Trim leading/trailing whitespace
                RELEASE_NOTES=$(echo "$RELEASE_NOTES" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
                
                if [ -z "$RELEASE_NOTES" ]; then
                    echo -e "${YELLOW}⚠️  Could not find version ${VERSION} in CHANGELOG.md${NC}"
                    RELEASE_NOTES="Release version ${VERSION}

See [CHANGELOG.md](CHANGELOG.md) for details."
                else
                    echo -e "${GREEN}✅ Extracted release notes from CHANGELOG.md${NC}"
                fi
            else
                echo -e "${YELLOW}⚠️  CHANGELOG.md not found${NC}"
                RELEASE_NOTES="Release version ${VERSION}"
            fi
            
            # Create temporary file for release notes (gh release create needs file or stdin)
            NOTES_FILE=$(mktemp)
            echo "$RELEASE_NOTES" > "$NOTES_FILE"
            
            echo -e "${YELLOW}Creating GitHub Release...${NC}"
            if gh release create "${TAG}" \
                --title "Release ${VERSION}" \
                --notes-file "$NOTES_FILE" \
                --repo "aipartnerup/${PROJECT_NAME}"; then
                echo -e "${GREEN}✅ GitHub Release created successfully${NC}"
                echo -e "${CYAN}   https://github.com/aipartnerup/${PROJECT_NAME}/releases/tag/${TAG}${NC}"
            else
                echo -e "${RED}❌ Failed to create GitHub Release${NC}"
                echo -e "${YELLOW}   You may need to authenticate: gh auth login${NC}"
                echo -e "${YELLOW}   Or check your GitHub permissions${NC}"
            fi
            
            # Clean up temporary file
            rm -f "$NOTES_FILE"
        else
            echo -e "${YELLOW}⚠️  Skipped GitHub Release creation${NC}"
        fi
        fi
    else
        echo -e "${YELLOW}⚠️  GitHub CLI (gh) not found${NC}"
        echo ""
        echo -e "${CYAN}   To install GitHub CLI:${NC}"
        echo -e "${CYAN}   • macOS:    brew install gh${NC}"
    echo -e "${CYAN}   • Linux:    See https://github.com/cli/cli/blob/trunk/docs/install_linux.md${NC}"
    echo -e "${CYAN}     - Debian/Ubuntu: sudo apt install gh${NC}"
    echo -e "${CYAN}     - Fedora/RHEL:   sudo dnf install gh${NC}"
        echo -e "${CYAN}     - Arch Linux:     sudo pacman -S github-cli${NC}"
        echo -e "${CYAN}   • Windows:  See https://cli.github.com/${NC}"
        echo -e "${CYAN}   • Or visit: https://cli.github.com/${NC}"
        echo ""
        echo -e "${CYAN}   After installation, authenticate with:${NC}"
        echo -e "${CYAN}     gh auth login${NC}"
        echo ""
        echo -e "${CYAN}   Create release manually at:${NC}"
        echo -e "${CYAN}   https://github.com/aipartnerup/${PROJECT_NAME}/releases/new${NC}"
        if [ -f "CHANGELOG.md" ]; then
            # Show a preview of what would be in the release notes
            PREVIEW=$(awk "
                /^## \[${VERSION}\]/ {found=1; next}
                found && /^## \[/ {exit}
                found {print}
            " CHANGELOG.md | head -20)
            if [ -n "$PREVIEW" ]; then
                echo -e "${CYAN}   Release notes preview from CHANGELOG.md:${NC}"
                echo "$PREVIEW" | sed 's/^/     /'
            else
                echo -e "${CYAN}   (Could not extract from CHANGELOG.md)${NC}"
            fi
        fi
    fi
    echo ""
    return 0
}

step7_upload_pypi() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Step 7: Upload to PyPI${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    
    if command -v pip &> /dev/null; then
        if pip index versions "${PROJECT_NAME}" 2>/dev/null | grep -q "${VERSION}"; then
            echo -e "${GREEN}✅ Version ${VERSION} already exists on PyPI${NC}"
            if ! ask_yn "Upload anyway? (will fail if version exists)" "n"; then
                SKIP_PYPI=true
            else
                SKIP_PYPI=false
            fi
        else
            SKIP_PYPI=false
        fi
    else
        SKIP_PYPI=false
    fi
    
    if [ "$SKIP_PYPI" = false ]; then
        if ! command -v twine &> /dev/null; then
            echo -e "${RED}❌ Error: twine not found${NC}"
            echo -e "${YELLOW}   Install with: pip install twine${NC}"
            return 1
        fi
        
        if ask_yn "Upload to PyPI?" "y"; then
            echo -e "${YELLOW}Uploading to PyPI...${NC}"
            if ! twine upload dist/*; then
                echo -e "${RED}❌ Upload to PyPI failed${NC}"
                return 1
            fi
            echo -e "${GREEN}✅ Successfully uploaded to PyPI!${NC}"
        else
            echo -e "${YELLOW}⚠️  Skipped PyPI upload${NC}"
            echo -e "${CYAN}   Upload manually with: twine upload dist/*${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Skipped PyPI upload (version already exists)${NC}"
    fi
    echo ""
    return 0
}

step_summary() {
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  Release Summary                                          ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Version:     ${CYAN}${VERSION}${NC}"
    echo -e "  Tag:         ${CYAN}${TAG}${NC}"
    echo ""
    
    if check_release_exists; then
        echo -e "  ${GREEN}✅${NC} GitHub Release:"
        echo -e "     https://github.com/aipartnerup/${PROJECT_NAME}/releases/tag/${TAG}"
    elif check_tag_exists; then
        echo -e "  ${YELLOW}⚠️${NC}  GitHub Release: Tag exists but release not created"
        echo -e "     Create at: https://github.com/aipartnerup/${PROJECT_NAME}/releases/new"
    else
        echo -e "  ${YELLOW}⚠️${NC}  GitHub Release: Not created yet"
        echo -e "     Create at: https://github.com/aipartnerup/${PROJECT_NAME}/releases/new"
    fi
    
    if [ -d "dist" ] && [ "$(ls -A dist/*.whl dist/*.tar.gz 2>/dev/null | wc -l)" -gt 0 ]; then
        echo -e "  ${GREEN}✅${NC} Package built: dist/"
    else
        echo -e "  ${YELLOW}⚠️${NC}  Package: Not built"
    fi
    
    if command -v pip &> /dev/null && pip index versions "${PROJECT_NAME}" 2>/dev/null | grep -q "${VERSION}"; then
        echo -e "  ${GREEN}✅${NC} PyPI: https://pypi.org/project/${PROJECT_NAME}/${VERSION}/"
    else
        echo -e "  ${YELLOW}⚠️${NC}  PyPI: Not uploaded yet"
    fi
    
    echo ""
    echo -e "${GREEN}✨ Release script completed!${NC}"
    echo ""
    echo -e "${CYAN}Next steps:${NC}"
    echo "  1. Verify installation: pip install --upgrade ${PROJECT_NAME}==${VERSION}"
    echo "  2. Update CHANGELOG.md with [Unreleased] section for next version"
    echo ""
    return 0
}

# Main execution logic
# Show menu first, then execute selected steps
while true; do
    show_main_menu
    
    # Use the global variable set by show_main_menu
    SELECTION="$MENU_SELECTION"
    
    if [ -z "$SELECTION" ]; then
        echo -e "${RED}No selection made. Please try again.${NC}"
        continue
    fi
    
    case "$SELECTION" in
        all|ALL|a|A)
            # Execute all steps
            echo ""
            echo -e "${CYAN}Executing all steps with interactive prompts...${NC}"
            echo ""
            
            # First verify version (required)
            if ! step1_version_verification; then
                echo -e "${RED}Version verification failed. Exiting.${NC}"
                exit 1
            fi
            
            step2_check_status
            step3_clean_build || echo -e "${YELLOW}Step 3 failed, continuing...${NC}"
            step4_build_package || echo -e "${YELLOW}Step 4 failed, continuing...${NC}"
            step5_check_package || echo -e "${YELLOW}Step 5 failed, continuing...${NC}"
            step6_git_tag || echo -e "${YELLOW}Step 6 failed, continuing...${NC}"
            step6_5_create_github_release || echo -e "${YELLOW}Step 6.5 failed, continuing...${NC}"
            step7_upload_pypi || echo -e "${YELLOW}Step 7 failed, continuing...${NC}"
            step_summary
            break
            ;;
        1)
            if ! step1_version_verification; then
                echo -e "${RED}Version verification failed.${NC}"
            fi
            ;;
        2)
            step2_check_status
            ;;
        3)
            step3_clean_build
            ;;
        4)
            step4_build_package
            ;;
        5)
            step5_check_package
            ;;
        6)
            step6_git_tag
            ;;
        7)
            step6_5_create_github_release
            ;;
        8)
            step7_upload_pypi
            ;;
        9)
            step_summary
            ;;
        0)
            # Exit
            echo -e "${CYAN}Exiting...${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid selection. Please choose a valid option.${NC}"
            ;;
    esac
done

