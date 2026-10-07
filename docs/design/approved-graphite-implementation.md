# Approved graphite direction — two-page source preview

The user accepted the complete direction with “可以，右边还可以继续优化”. The parent then refined the right side within that scope and supplied its visible-pixel specification. The design reference is Library `libfile_b7a5e9fa7bf48191be8133b87aa77c55`, version 1, `exec-53816e8f-ede7-424c-bbc2-f916ba400bc5.png`. Local official Library read returned extracted text and explicitly warned that native image pixels were unavailable; we did not claim to inspect that reference image or repeat the previously failed Windows helper path.

`ApprovedWindow` implements that supplied specification in a separate opt-in two-page shell, leaving the rejected reference shell and existing production launch intact. It reuses existing widget connections, settings models and actual cursor assets. Default review theme is graphite; the light theme uses the same geometry. No install, Apply, startup or updater action was performed to produce evidence.

## Implemented comparison to the supplied specification

- 190 DIP blue-graphite sidebar, four existing navigation entries, blue selected row; native Windows frame retained. Main review window is 1100×830.
- Title, compact toolbar and two real light/dark cursor stages, followed by Shape, Palette, three property rows and fixed bottom actions. Groups share their left edge and full content width; when scrolling is required the scrollbar consumes its normal small width. Content caps at 960 DIP in wide windows.
- Six real families in one equal-width row, one common panel; eight actual paired previews in a 4×2 common panel. Unselected specimens have transparent backgrounds/borders. Only the selected specimen gets a blue edge and subtle fill. Shape panel is approximately 86 DIP; palette panel approximately 146 DIP before its heading.
- Palette heading shows the current short name, without a menu. Size, background adaptation and custom controls share one divided panel. Rows are approximately 38 DIP. History and reset stay available in the custom row. Bottom bar is fixed at 52 DIP.
- Settings uses the same tokens and compact grouped rows, retaining the visible distinction between immediate startup/pause actions and preferences submitted with Apply. Four-theme confirmation styling and safe default cancel remain unchanged.

## Intentional differences and remaining limitation

The reference cursor silhouettes are illustrative: the implementation uses the existing real rounded/family shapes and original press motion, not regenerated AI cursors. Native title-bar chrome is retained. Role selection remains an accessible 17-role Qt control with compact custom styling. History/reset are retained even though the design illustration omits their compatibility detail. At 880×620 the default 32 px screen exposes the six shapes and eight palettes; property rows require scrolling. At 64 px the larger fixed preview also moves some palette choices below the viewport. No target sizes were reduced to force all controls onto the screen. Custom colors expand within the same scrolling property area, keeping preview and Apply fixed.

The visual material is **opaque graphite levels and thin boundaries, not true frosted blur**. A hidden instance of this new approved Mock shell accepted the documented DWM Mica request and restored it on close; default-off, simulated high contrast and unsupported-platform fallback were verified with zero system cursor operations. `.local/approved-ui/candidate-check-windows.json` records that no final material pixels were proven. Native-frame translucent client integration remains unimplemented; Qt's documented translucent QWidget route on Windows needs a frameless window, which would change drag/resize/Snap/system-menu responsibilities. That larger change is not silently introduced here. See `windows-material-feasibility.md` for official sources and constraints.

## Evidence and safe review

Use `.local/SAFE-Pointer-Approved-Preview.cmd`. Its single Qt inheritance chain uses the existing guarded updater callbacks and service-isolation context; the Mock backend rejects system operations. It reads no user configuration and writes no saved preferences. Production entry and previous SAFE previews are unchanged. Only these two new pages are ready for user review; Motion and Test retain prior behavior.

`.local/approved-ui/pages/` contains 48 real Qt captures: both pages, shallow/deep scroll, draft state, focus and 64 px, in light/dark at 880×620, 1100×830 and 1800×900. `custom-64/` adds six 880 px custom-expanded/top/bottom/focus captures. `dialogs/` contains 60 simulated palette/button-state captures. Widget capture excludes the native frame and DWM composition; it is not a full desktop screenshot or material proof.

Full `python -m unittest discover -s tests` ran 194 tests: OK, one skip. The four added approved-shell tests cover geometry at all three widths, fixed Apply, original data, real shape/palette/history/custom edits, all four confirmation theme combinations with cancel retaining the draft, and guarded update callbacks. Existing original-motion tests exercise the immutable 640 preview oracle and native resources. No new Windows package is claimed ready or built for this opt-in source preview, so no new packaged diagnosis was run. All previous packages and evidence are retained; no push.
