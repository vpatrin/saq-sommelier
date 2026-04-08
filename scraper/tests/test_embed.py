from scraper.embed import build_embedding_text, compute_embedding_hash


class TestBuildEmbeddingText:
    def test_formats_all_fields_into_structured_text_lines(self) -> None:
        text = build_embedding_text(
            category="Vin rouge",
            taste_tag="Aromatique et souple",
            tasting_profile={
                "corps": "mi-corsé",
                "sucre": "sec",
                "acidite": "présente",
                "arome": ["cassis", "prune", "sous-bois"],
            },
            grape_blend=[{"code": "MALB", "pct": 96}, {"code": "SYRA", "pct": 4}],
            producer="Bodega Catena Zapata",
            region="Mendoza",
            appellation="Valle de Uco",
            designation="DOC",
            country="Argentine",
            vintage="2021",
            description="A bold Malbec with deep fruit concentration.",
        )

        lines = text.split("\n")
        assert lines[0] == "Vin rouge | Aromatique et souple | mi-corsé, sec, présente"
        assert lines[1] == (
            "Bodega Catena Zapata | MALB 96%, SYRA 4%"
            " | Mendoza, Valle de Uco, DOC, Argentine | 2021"
        )
        assert lines[2] == "Arômes: cassis, prune, sous-bois"
        assert lines[3] == "A bold Malbec with deep fruit concentration."

    def test_minimal_product(self) -> None:
        text = build_embedding_text(description="Simple wine.")
        assert text == "Simple wine."

    def test_empty_product(self) -> None:
        text = build_embedding_text()
        assert text == ""

    def test_taste_tag_only(self) -> None:
        text = build_embedding_text(taste_tag="Fruité et généreux")
        assert text == "Fruité et généreux"

    def test_falls_back_to_grape_when_no_blend(self) -> None:
        text = build_embedding_text(grape="Cabernet Sauvignon", country="France")
        assert text == "Cabernet Sauvignon | France"

    def test_grape_blend_takes_precedence_over_grape(self) -> None:
        text = build_embedding_text(
            grape="Malbec",
            grape_blend=[{"code": "MALB", "pct": 100}],
            country="Argentine",
        )
        assert text == "MALB 100% | Argentine"

    def test_origin_partial(self) -> None:
        text = build_embedding_text(region="Bordeaux", country="France")
        assert text == "Bordeaux, France"

    def test_arome_as_string(self) -> None:
        text = build_embedding_text(
            tasting_profile={"arome": "cassis et prune"},
        )
        assert text == "Arômes: cassis et prune"

    def test_profile_without_body_fields(self) -> None:
        """Profile with only arome — no line 1, just aromas."""
        text = build_embedding_text(
            tasting_profile={"arome": ["cerise"]},
        )
        assert text == "Arômes: cerise"

    def test_profile_body_without_arome(self) -> None:
        text = build_embedding_text(
            tasting_profile={"corps": "corsé", "sucre": "sec"},
        )
        assert text == "corsé, sec"

    def test_category_in_line1(self) -> None:
        text = build_embedding_text(category="Vin rouge", taste_tag="Fruité et généreux")
        assert text == "Vin rouge | Fruité et généreux"

    def test_category_only(self) -> None:
        text = build_embedding_text(category="Champagne et mousseux")
        assert text == "Champagne et mousseux"


class TestComputeEmbeddingHash:
    def test_same_input_same_hash(self) -> None:
        attrs = {"taste_tag": "Fruité", "region": "Bordeaux"}
        assert compute_embedding_hash(attrs) == compute_embedding_hash(attrs)

    def test_different_input_different_hash(self) -> None:
        h1 = compute_embedding_hash({"taste_tag": "Fruité"})
        h2 = compute_embedding_hash({"taste_tag": "Corsé"})
        assert h1 != h2

    def test_empty_attrs(self) -> None:
        h = compute_embedding_hash({})
        assert isinstance(h, str)
        assert len(h) == 64  # SHA256 hex

    def test_includes_tasting_profile_subfields(self) -> None:
        h1 = compute_embedding_hash({"tasting_profile": {"corps": "corsé"}})
        h2 = compute_embedding_hash({"tasting_profile": {"corps": "léger"}})
        assert h1 != h2

    def test_ignores_non_hash_fields(self) -> None:
        """Price, availability, rating are NOT in the hash."""
        base = {"taste_tag": "Fruité"}
        h1 = compute_embedding_hash(base)
        h2 = compute_embedding_hash({**base, "price": "29.99", "online_availability": True})
        assert h1 == h2

    def test_order_independent_of_dict_ordering(self) -> None:
        """Hash uses fixed field order, not dict iteration order."""
        h1 = compute_embedding_hash({"region": "Bordeaux", "taste_tag": "Fruité"})
        h2 = compute_embedding_hash({"taste_tag": "Fruité", "region": "Bordeaux"})
        assert h1 == h2
