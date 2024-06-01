from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, DataTable, Header, Markdown, Log


class Status(Screen):
    BINDINGS = [("q", "app.pop_screen", "Go back")]

    def compose(self) -> ComposeResult:
        yield Markdown()
        yield Header()
        yield Footer()


class FetaApp(App):
    """Feta - Fediverse Tui App"""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("j", "cursor_down"),
        ("k", "cursor_up"),
        ("l", "select_status"),
    ]

    def compose(self) -> ComposeResult:
        yield DataTable(id="timeline", cursor_type="row", show_header=False)
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Feta"
        self.sub_title = "Home timeline"
        self.install_screen(Status(), name="status")

        timeline = self.query_one(DataTable)
        timeline.add_columns("id", "date", "user", "title")
        timeline.add_rows(
            [
                (
                    1,
                    "Jun 01",
                    "@user",
                    "Example post...",
                ),
                (
                    2,
                    "Jun 01",
                    "@user",
                    "Example post...",
                ),
            ]
        )

    def on_data_table_row_selected(self) -> None:
        self.app.push_screen("status")

    def action_cursor_up(self) -> None:
        self.query_one(DataTable).action_cursor_up()

    def action_cursor_down(self) -> None:
        self.query_one(DataTable).action_cursor_down()

    def action_select_status(self) -> None:
        self.query_one(DataTable).action_select_cursor()


if __name__ == "__main__":
    app = FetaApp()
    app.run()
