"""
Phase 13: the accessibility and responsive-layout pass (PRD nonfunctional requirements; AC44).
Every page an Admin can open is parsed and checked for the structural rules a test can see:
headings, labelled controls, named links and buttons, table headers, and wide content that
scrolls inside its card instead of the page.
"""

from html.parser import HTMLParser

from django.test import TestCase

from core.tests.test_permission_review import ReviewData

LABELLED_INPUTS = {
    "text",
    "email",
    "url",
    "tel",
    "password",
    "number",
    "search",
    "checkbox",
    "radio",
}


class PageAudit(HTMLParser):
    """Collects what the checks need in one pass over a page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.headings = []  # levels in document order
        self.label_targets = set()
        self.controls = []  # (id, has aria-label, inside a <label>)
        self.label_depth = 0
        self.named = []  # links and buttons: [tag, text, has aria-label, attrs]
        self.open_named = []
        self.th_without_scope = 0
        self.tables_outside_scroller = 0
        self.stack = []  # (tag, class) of open elements
        self.drawer_classes = None

    VOID = {"input", "br", "img", "meta", "link", "hr", "source", "col", "area", "wbr"}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        css = attrs.get("class") or ""
        if tag == "html":
            self.lang = attrs.get("lang")
        if "drawer" in css.split() and self.drawer_classes is None:
            self.drawer_classes = css
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(int(tag[1]))
        if tag == "label":
            self.label_depth += 1
            if attrs.get("for"):
                self.label_targets.add(attrs["for"])
        is_control = tag in {"select", "textarea"} or (
            tag == "input" and attrs.get("type", "text") in LABELLED_INPUTS
        )
        if is_control and "drawer-toggle" not in css:
            self.controls.append((attrs.get("id"), "aria-label" in attrs, self.label_depth > 0))
        if tag in {"a", "button"}:
            entry = [tag, "", "aria-label" in attrs, attrs]
            self.named.append(entry)
            self.open_named.append(entry)
        if tag == "th" and "scope" not in attrs:
            self.th_without_scope += 1
        if tag == "table" and not any("overflow-x-auto" in c for _, c in self.stack):
            self.tables_outside_scroller += 1
        if tag not in self.VOID:
            self.stack.append((tag, css))

    def handle_endtag(self, tag):
        if tag == "label":
            self.label_depth -= 1
        if tag in {"a", "button"} and self.open_named:
            self.open_named.pop()
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        for entry in self.open_named:
            entry[1] += data


class AccessibilityReviewTests(ReviewData, TestCase):
    def audits(self):
        self.client.force_login(self.admin)
        for case in self.cases():
            if case.method != "get":
                continue
            response = self.client.get(case.url())
            self.assertEqual(response.status_code, 200, str(case))
            self.assertTemplateUsed(response, "base.html")
            audit = PageAudit()
            audit.feed(response.content.decode())
            yield str(case), audit

    def test_every_page_has_a_language_and_one_h1(self):
        for page, audit in self.audits():
            with self.subTest(page=page):
                self.assertEqual(audit.lang, "en")
                self.assertEqual(audit.headings.count(1), 1)
                self.assertEqual(audit.headings[0], 1, "the first heading is the h1")

    def test_heading_levels_never_skip(self):
        for page, audit in self.audits():
            with self.subTest(page=page):
                for previous, level in zip(audit.headings, audit.headings[1:], strict=False):
                    self.assertLessEqual(level, previous + 1, audit.headings)

    def test_every_form_control_is_labelled(self):
        for page, audit in self.audits():
            with self.subTest(page=page):
                for control_id, aria, wrapped in audit.controls:
                    self.assertTrue(
                        control_id in audit.label_targets or aria or wrapped,
                        f"unlabelled control {control_id!r}",
                    )

    def test_every_link_and_button_has_a_name(self):
        for page, audit in self.audits():
            with self.subTest(page=page):
                for tag, text, aria, attrs in audit.named:
                    self.assertTrue(text.strip() or aria, f"unnamed <{tag}> {attrs}")

    def test_table_headers_have_a_scope(self):
        for page, audit in self.audits():
            with self.subTest(page=page):
                self.assertEqual(audit.th_without_scope, 0)

    def test_wide_content_scrolls_inside_its_card_not_the_page(self):
        # At phone width a table scrolls inside its card, and the drawer's content column can
        # shrink below its content's width, so the page itself never scrolls sideways.
        for page, audit in self.audits():
            with self.subTest(page=page):
                self.assertEqual(audit.tables_outside_scroller, 0)
                self.assertIn("auto-cols-[max-content_minmax(0,1fr)]", audit.drawer_classes)
