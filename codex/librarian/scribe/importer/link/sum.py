from codex.librarian.scribe.importer.link.delete import LinkImporterDelete


class LinkSumImporter(LinkImporterDelete):
    def sum_path_ops(self, key):
        """Sum all the operations for the key."""
        count = 0
        for fields in self.metadata[key].values():
            for ops in fields.values():
                count += len(ops)
        return count

    def sum_ops(self, key):
        """Sum all the operations for the key."""
        return sum(len(ops) for ops in self.metadata[key].values())
