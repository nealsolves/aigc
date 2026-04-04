import { helpContent } from './helpContent'

describe('helpContent', () => {
  it('has an architecture entry and entries for all 7 labs', () => {
    expect(helpContent[0]).toBeDefined()
    for (let i = 1; i <= 7; i++) {
      expect(helpContent[i]).toBeDefined()
    }
  })

  it('every guide has a non-empty title, overview, whyItMatters, and takeaway', () => {
    for (let i = 0; i <= 7; i++) {
      expect(helpContent[i].title.length).toBeGreaterThan(0)
      expect(helpContent[i].overview.length).toBeGreaterThan(0)
      expect(helpContent[i].whyItMatters.length).toBeGreaterThan(0)
      expect(helpContent[i].takeaway.length).toBeGreaterThan(0)
    }
  })

  it('every guide has at least 3 steps', () => {
    for (let i = 0; i <= 7; i++) {
      expect(helpContent[i].steps.length).toBeGreaterThanOrEqual(3)
    }
  })

  it('every guide has framework sections for learning and navigation', () => {
    for (let i = 0; i <= 7; i++) {
      expect(helpContent[i].whatThisLabShows.length).toBeGreaterThanOrEqual(2)
      expect(helpContent[i].howToNavigate.length).toBeGreaterThanOrEqual(2)
    }
  })

  it('every step has a non-empty title and instruction', () => {
    for (let i = 0; i <= 7; i++) {
      for (const step of helpContent[i].steps) {
        expect(step.title.length).toBeGreaterThan(0)
        expect(step.instruction.length).toBeGreaterThan(0)
      }
    }
  })

  // Fidelity tests — catch content drift between help drawer and actual UI

  it('architecture overview does not claim signing is always present', () => {
    const overview = helpContent[0].overview
    expect(overview).not.toMatch(/signed audit record regardless/i)
    // Signing should be described as opt-in
    expect(overview).toMatch(/opt-in/i)
  })

  it('architecture pipeline step includes pre_output gates', () => {
    const pipelineStep = helpContent[0].steps.find(s => s.title.toLowerCase().includes('pipeline'))
    expect(pipelineStep).toBeDefined()
    expect(pipelineStep!.instruction).toMatch(/pre_output/i)
  })

  it('architecture framework explains that AIGC is a runtime governance layer', () => {
    expect(helpContent[0].overview).toMatch(/runtime governance layer/i)
    expect(helpContent[0].takeaway).toMatch(/deterministic governance wrapper/i)
  })

  it('lab 1 framework keeps risk modes and threshold behavior explicit', () => {
    const content = [
      helpContent[1].overview,
      helpContent[1].whyItMatters,
      helpContent[1].whatThisLabShows.join(' '),
      helpContent[1].howToNavigate.join(' '),
      helpContent[1].steps.map(s => s.instruction + (s.tip ?? '')).join(' '),
    ].join(' ')
    expect(content).toMatch(/strict/i)
    expect(content).toMatch(/risk_scored/i)
    expect(content).toMatch(/warn_only/i)
    expect(content).toMatch(/0\.70|0.7/i)
  })

  it('lab 4 glossary uses intersect, union, replace — not merge/override/strict strategy', () => {
    const glossary = helpContent[4].glossary ?? []
    const terms = glossary.map(g => g.term.toLowerCase())
    expect(terms).toContain('intersect')
    expect(terms).toContain('union')
    expect(terms).toContain('replace')
    expect(terms).not.toContain('merge strategy')
    expect(terms).not.toContain('override strategy')
    expect(terms).not.toContain('strict strategy')
  })

  it('lab 5 steps do not mention EnvLoader or RegistryLoader', () => {
    const content = helpContent[5].steps.map(s => s.instruction + (s.tip ?? '')).join(' ')
    const glossaryTerms = (helpContent[5].glossary ?? []).map(g => g.term).join(' ')
    expect(content + glossaryTerms).not.toMatch(/EnvLoader/i)
    expect(content + glossaryTerms).not.toMatch(/RegistryLoader/i)
  })

  it('lab 5 glossary includes FileSystemLoader and InMemoryPolicyLoader', () => {
    const terms = (helpContent[5].glossary ?? []).map(g => g.term)
    expect(terms.some(t => t.toLowerCase().includes('filepolicyloader'))).toBe(true)
    expect(terms.some(t => t.toLowerCase().includes('inmemorypolicyloader') || t.toLowerCase().includes('inmemoryloader'))).toBe(true)
  })

  it('lab 5 navigation references the current tab names', () => {
    const content = helpContent[5].howToNavigate.join(' ')
    expect(content).toMatch(/Loaders/i)
    expect(content).toMatch(/Versioning/i)
    expect(content).toMatch(/Testing/i)
  })

  it('lab 6 steps do not claim different sets of gates per scenario', () => {
    const content = helpContent[6].steps.map(s => s.instruction + (s.tip ?? '')).join(' ')
    expect(content).not.toMatch(/different set.*gate/i)
  })

  it('lab 6 glossary includes gates_evaluated', () => {
    const terms = (helpContent[6].glossary ?? []).map(g => g.term.toLowerCase())
    expect(terms).toContain('gates_evaluated')
  })

  it('lab 6 framework names all four supported insertion points', () => {
    const content = [
      helpContent[6].overview,
      helpContent[6].whatThisLabShows.join(' '),
      helpContent[6].steps.map(s => s.instruction + (s.tip ?? '')).join(' '),
    ].join(' ')
    expect(content).toMatch(/pre_authorization/i)
    expect(content).toMatch(/post_authorization/i)
    expect(content).toMatch(/pre_output/i)
    expect(content).toMatch(/post_output/i)
  })

  it('lab 7 describes sample mode as an explicit action, not silent default', () => {
    const content = [
      helpContent[7].overview,
      helpContent[7].whatThisLabShows.join(' '),
      helpContent[7].steps.map(s => s.instruction + (s.tip ?? '')).join(' '),
    ].join(' ')
    // Must mention explicit loading of sample data
    expect(content).toMatch(/load sample data/i)
    // Must not imply it is the default or silent
    expect(content).not.toMatch(/silently/i)
  })

  it('lab 7 does not claim signed indicator proves verification', () => {
    const content = helpContent[7].steps.map(s => s.instruction + (s.tip ?? '')).join(' ')
    const glossary = (helpContent[7].glossary ?? []).map(g => g.definition).join(' ')
    expect(content + glossary).not.toMatch(/valid hmac signature/i)
  })

  it('lab 7 framework mentions both UI export formats and the CLI handoff', () => {
    const content = [
      helpContent[7].whatThisLabShows.join(' '),
      helpContent[7].howToNavigate.join(' '),
      helpContent[7].steps.map(s => s.instruction + (s.tip ?? '')).join(' '),
    ].join(' ')
    expect(content).toMatch(/JSON/i)
    expect(content).toMatch(/CSV/i)
    expect(content).toMatch(/aigc compliance export/i)
  })
})
