from folio.ingest import Section, chunk


def test_small_section_single_chunk():
    chunks = chunk([Section("Hello world.", page=3, heading="H")], size=100, overlap=10)
    assert len(chunks) == 1
    assert (chunks[0].page, chunks[0].heading, chunks[0].text) == (3, "H", "Hello world.")


def test_long_text_splits_within_limit_with_overlap():
    sentences = " ".join(f"Sentence number {i} talks about topic {i}." for i in range(400))
    chunks = chunk([Section(sentences)], size=100, overlap=20)
    assert len(chunks) > 5
    assert all(len(c.text) <= 100 * 4 + 20 * 4 + 10 for c in chunks)
    tail = chunks[0].text[-30:]
    assert tail.split()[-1] in chunks[1].text


def test_sections_never_merge_and_keep_metadata():
    sections = [Section("Page one.", page=1), Section("Page two.", page=2)]
    chunks = chunk(sections, size=500, overlap=50)
    assert [c.page for c in chunks] == [1, 2]
    assert [c.ord for c in chunks] == [0, 1]


def test_code_fence_kept_whole():
    code = "```python\ndef f():\n\n    return 1\n```"
    chunks = chunk([Section(f"Intro paragraph.\n\n{code}\n\nOutro.")], size=500, overlap=0)
    assert code in chunks[0].text


def test_offsets_point_into_section():
    text = "First paragraph.\n\nSecond paragraph."
    chunks = chunk([Section(text)], size=500, overlap=0)
    assert text[chunks[0].start_char : chunks[0].end_char] == text
