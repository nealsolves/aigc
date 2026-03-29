import { helpContent } from './helpContent'

describe('helpContent', () => {
  it('has entries for all 7 labs', () => {
    for (let i = 1; i <= 7; i++) {
      expect(helpContent[i]).toBeDefined()
    }
  })

  it('every lab has a non-empty title and overview', () => {
    for (let i = 1; i <= 7; i++) {
      expect(helpContent[i].title.length).toBeGreaterThan(0)
      expect(helpContent[i].overview.length).toBeGreaterThan(0)
    }
  })

  it('every lab has at least 3 steps', () => {
    for (let i = 1; i <= 7; i++) {
      expect(helpContent[i].steps.length).toBeGreaterThanOrEqual(3)
    }
  })

  it('every step has a non-empty title and instruction', () => {
    for (let i = 1; i <= 7; i++) {
      for (const step of helpContent[i].steps) {
        expect(step.title.length).toBeGreaterThan(0)
        expect(step.instruction.length).toBeGreaterThan(0)
      }
    }
  })
})
