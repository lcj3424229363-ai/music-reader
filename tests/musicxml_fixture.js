'use strict';

function pitch(step, octave, accidental = '') {
  return { step, octave, accidental, display: `${step}${accidental}${octave}` };
}

function note(step, octave, options = {}) {
  return {
    kind: 'note',
    pitches: [pitch(step, octave, options.accidental || '')],
    duration: options.duration || '4',
    dotted: options.dotted || 0,
    units: options.units ?? 8,
    tieStart: false,
    tieStop: false,
    slurStart: false,
    slurStop: false,
    fermata: false,
    dynamic: '',
    tupletType: '',
    tupletPosition: '',
    ...options
  };
}

function voice(id, entries) {
  return { id, role: '', entries };
}

function fixture() {
  const treble = {
    id: 'treble', staffNumber: 1, label: 'Treble', clef: 'treble',
    measures: [{
      number: 1, beginBarline: 'repeat-begin', endBarline: 'double',
      voices: [
        voice('1', [
          note('F', 5, {
            accidental: '#', duration: '4', dotted: 1, units: 12,
            pitches: [pitch('F', 5, '#'), pitch('A', 5), pitch('C', 6, '#')],
            tieStart: true, slurStart: true, dynamic: 'mf', articulation: 'accent',
            textMark: 'dolce & cantabile', chordSymbol: 'F#maj7/C#', fingering: '2',
            grace: pitch('E', 5, 'n'), breath: true, arpeggiate: true,
            rehearsalMark: 'A1', volta: 1
          }),
          note('F', 5, { accidental: 'n', duration: '8', units: 4, tieStop: true, slurStop: true, ornament: 'trill' }),
          note('A', 5, { duration: '2', units: 16, fermata: true, phraseStart: true, phraseStop: true })
        ]),
        voice('2', [note('C', 4, { duration: '1', units: 32, chordSymbol: 'D7/F#' })])
      ]
    }]
  };
  const bass = {
    id: 'bass', staffNumber: 2, label: 'Bass', clef: 'bass',
    measures: [{
      number: 1, beginBarline: 'repeat-begin', endBarline: 'double',
      voices: [
        voice('1', [note('E', 3, { duration: '2', units: 16 }), note('F', 3, { duration: '2', units: 16 })]),
        voice('2', [
          {
            ...note('C', 3, {
              duration: '2', units: 16, dynamic: 'p', pedal: 'start',
              textMark: 'rest cue', chordSymbol: 'Fm'
            }),
            kind: 'rest', pitches: []
          },
          note('G', 2, { duration: '2', units: 16, pedal: 'stop', hairpin: 'cresc-start', chordSymbol: 'Cm7/G' })
        ])
      ]
    }]
  };
  return {
    title: 'Frontend roundtrip', timeSignature: '4/4', keySignature: 'Am',
    tempo: 96, anacrusis: true, measureCount: 1, staves: [treble, bass]
  };
}

module.exports = { fixture, note, pitch, voice };
