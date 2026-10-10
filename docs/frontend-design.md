# GreenLens frontend design

This is a mobile field tool for residents, RWAs and ward officers. The camera,
historical satellite readings and three data-summary actions drive the demo.
The design preserves the GreenLens wordmark, forest-green background, lime
accent and explicit preview/GPS distinction. Noto Sans is self-hosted under
`public/fonts` with its SIL Open Font License. The Latin variable font is about
35 KB and covers weights 400 to 750; system fonts cover other glyphs.

The initial rearrangement replaces overlapping readings with one stable card,
places camera and GPS controls below the scene, and puts settings and provenance
in a disclosure. Historical dates remain visible. Heat colours use the rounded
minimum and maximum of the available grid, while NDVI uses 0 to 1.

Design dials: variance 3/10, motion 3/10, density 5/10. A calm, readable tool
matters more than decorative animation. The implementation uses existing React,
Three.js and native CSS without new dependencies.

| Interaction | Feedback | Duration |
| --- | --- | --- |
| Choose Surface heat or Vegetation | Selection background slides to the active button | 220 ms |
| Change layer or preview mode | New reading enters with 3 px movement; values appear immediately | 180 ms |
| Press a button | 1 px press movement and colour feedback | 160 ms |
| Receive a summary | Result enters with 5 px movement | 220 ms |
| Open Controls & sources | Content enters with 5 px movement | 180 ms |
| Camera becomes live | Video becomes visible | 180 ms |

Compass changes and environmental values do not animate or count up. There are
no continuous decorative loops. Reduced-motion preferences disable all listed
animation and transitions. The selected layer is also communicated by text
colour and `aria-pressed`, independent of animation.

[Figma design](https://www.figma.com/design/VDfG5HRHCki1Q8ZWh3n209?node-id=10-11) and
[query architecture](https://www.figma.com/board/7EO8wqIqn2jv6kEJB2vmE2)
are available for the team. The diagram distinguishes the running local SAM
API from the AWS deployment that was pending when the diagram was drawn. The API and Amplify HTTPS frontend are now deployed; direct CloudFront provisioning awaits account verification. The live page was captured
as a layout reference; the final Figma screen uses editable controls and text.

Figma motion node `12:328` maps to `.measurement-card`. Its exported motion
uses opacity 0.65 to 1 and vertical movement 3 px to 0 over the first 180 ms
of a 2-second timeline, with ease-out `(0, 0, 0.58, 1)`, then holds. Native CSS
preserves those values. The export's infinite repeat is intentionally disabled
in the app: this feedback plays once per layer or preview-mode change.
The Three.js mesh and material are reused across heading changes and disposed
when the overlay unmounts; no render loop runs while the view is idle.

To test, switch the two layers, request a data summary, and expand the controls.
Enable Reduce Motion in the device accessibility settings, reload and repeat:
each state change should become immediate. Test on a narrow phone and desktop;
heading controls, dates and measurement labels must remain readable.

Verification on 10 October 2026: all 12 frontend tests and the production build
pass. Browser checks at widths 320, 390 and 1024 px confirmed layer selection,
historical dates, heading-driven readings and no horizontal overflow. At 320 px,
the direction label was moved higher to clear the wrapped NDVI card, and camera
button text stays on one line. Physical camera/compass and device Reduce Motion
checks still require a real phone. The production bundle retains Vite's size
warning for Three.js.

The final editable Figma screen is frame `10:11`. The temporary capture frame
`5:2` remains in the file because the Starter plan exhausted its MCP tool quota
before cleanup. It can be removed manually; the final screen is independent of
that reference frame.
