; ===========================================================================
;  M A T R I X   R A I N   -   Commodore 64
; ---------------------------------------------------------------------------
;  Assemble:  make      (or: acme -f cbm -o matrix.prg src/matrix.asm)
;  Run:       LOAD"MATRIX",8,1  :  RUN          (or SYS 2061)
;  Exit:      press any key
; ---------------------------------------------------------------------------
;  WHAT CHANGED SINCE v1
;
;  1. SIX BRIGHTNESS STEPS INSTEAD OF THREE.
;     The VIC-II only has two greens, so extra shades cannot come from the
;     colour nybble.  They come from the GLYPH instead: at boot the program
;     builds its own character set in RAM holding every glyph three times -
;     full, 50% dithered and 25% dithered.  A dithered glyph lights fewer
;     pixels, so the same green reads as a darker green.  Combined with the
;     colour ramp that gives:
;
;         white full        ~100%   the leading character
;         lt.green full      ~76%
;         green full         ~35%
;         green 50% dither   ~18%
;         green 25% dither    ~9%
;         black               0%    erased
;
;     Dimming a cell is now "char = char + GLYPHS", which is why the three
;     copies are stored as three equal-size blocks.  No grey, no blue.
;
;  2. 85 GLYPHS INSTEAD OF 32: a-z, A-Z (mirrored, for that alien look),
;     0-9 and 23 PETSCII graphics, all lifted straight out of the character
;     ROM at boot - both ROM banks, so upper case, lower case and graphics
;     can live in the same character set at the same time.
;
;  3. Trail characters shimmer: the cell two rows behind the head is given a
;     fresh random glyph on its way past.
;
;  4. PALETTE switch below: classic green, amber phosphor or ice blue.
;
;  5. FONT switch: the built-in glyph set is an original 8x8 constructed
;     script drawn for this program - angular marks, half of them mirrored,
;     none of them readable as letters.  FONT = 0 goes back to the ROM
;     glyphs (a-z, A-Z, 0-9, PETSCII).
;
;  Still frame-locked to the lower border, still nowhere near a full frame
;  of work, so it cannot lag.
; ===========================================================================

; ---- build options --------------------------------------------------------
; Each of these can be overridden on the command line, e.g.
;     acme -DPALETTE=1 -DMUSIC=0 -f cbm -o matrix.prg src/matrix.asm
!ifndef PALETTE { PALETTE = 0 } ; 0 = green, 1 = amber, 2 = ice blue
!ifndef FONT    { FONT    = 1 } ; 1 = the built-in rain glyphs (original 8x8
                                ;     constructed script, designed for this)
                                ; 0 = glyphs pulled from the character ROM
                                ;     (a-z, A-Z, 0-9, PETSCII graphics)
!ifndef MIRROR  { MIRROR  = 1 } ; FONT 0 only: mirror the upper-case block
!ifndef MUSIC   { MUSIC   = 1 } ; 1 = play the tune, 0 = silent screen saver

; ---- constants ------------------------------------------------------------
SCREEN  = $0400
CHARSET = $3000                 ; 2 KB, VIC bank 0, must be 2 KB aligned
D018VAL = $1c                   ; screen $0400 + charset $3000
ROWS    = 25
COLS    = 40
GLYPHS  = 85                    ; glyphs per brightness block (3*85 = 255)

SRC     = $f7                   ; \
DST     = $f9                   ;  > zero page scratch, all free on a C64
PTR     = $fb                   ; /
TMP     = $fd
TMP2    = $fe

!if PALETTE = 0 {
C_HEAD  = $01                   ; white
C_TR1   = $0d                   ; light green
C_TR2   = $05                   ; green
}
!if PALETTE = 1 {
C_HEAD  = $01                   ; white
C_TR1   = $07                   ; yellow
C_TR2   = $08                   ; orange
}
!if PALETTE = 2 {
C_HEAD  = $01                   ; white
C_TR1   = $03                   ; cyan
C_TR2   = $0e                   ; light blue
}

RASLINE = $fa                   ; raster 250 = lower border, PAL and NTSC

; ===========================================================================
;  BASIC stub:  10 SYS 2061
; ===========================================================================
* = $0801
        !byte $0b,$08,$0a,$00,$9e,$32,$30,$36,$31,$00,$00,$00

; ===========================================================================
;  MACROS - everything in the inner loop is inlined
; ---------------------------------------------------------------------------
;  All of them take X = column and work out their own row from row,x.
;  A row above the top of the screen underflows to $FF.. and fails the
;  unsigned CMP #ROWS, so off-screen cells are skipped for free.
; ===========================================================================

; --- point PTR at SCREEN row Y, then put the column in Y -------------------
!macro scrptr {
        lda rowlo,y
        sta PTR
        lda rowhi,y
        sta PTR+1
        txa
        tay
}

; --- point PTR at COLOUR RAM row Y, then put the column in Y ---------------
;     $0400+n and $D800+n differ only in the high byte, by $D4.
!macro colptr {
        lda rowlo,y
        sta PTR
        lda colhi,y             ; = rowhi + $D4, precomputed
        sta PTR+1
        txa
        tay
}

; --- random glyph 0..GLYPHS-1 into A ---------------------------------------
;     Ten cycles, and no SID.  rndtab is 256 pre-folded glyph numbers built at
;     boot by an LFSR; the operand of the LDA is its own walking pointer, so
;     every place this macro is used gets an independent stream through the
;     table for free.  rndtab is page aligned, so the INC wraps in place.
!macro rndglyph {
.here   lda rndtab
        inc .here+1
}

; --- the head: fresh glyph, full brightness, head colour -------------------
!macro head {
        ldy row,x
        cpy #ROWS
        bcs .skip
        +scrptr
        +rndglyph
        sta (PTR),y             ; character
        lda PTR+1
        clc
        adc #$d4                ; same offset, colour RAM
        sta PTR+1
        lda #C_HEAD
        sta (PTR),y
.skip
}

; --- recolour the cell .off rows above the head ----------------------------
!macro fade .off, .col {
        lda row,x
        sec
        sbc #.off
        cmp #ROWS
        bcs .skip
        tay
        +colptr
        lda #.col
        sta (PTR),y
.skip
}

; --- recolour AND re-roll the glyph (the shimmer) --------------------------
!macro shimmer .off, .col {
        lda row,x
        sec
        sbc #.off
        cmp #ROWS
        bcs .skip
        tay
        +scrptr
        +rndglyph
        sta (PTR),y
        lda PTR+1
        clc
        adc #$d4
        sta PTR+1
        lda #.col
        sta (PTR),y
.skip
}

; --- knock one brightness step off the glyph, .off rows above the head -----
!macro dim .off {
        lda row,x
        sec
        sbc #.off
        cmp #ROWS
        bcs .skip
        tay
        +scrptr
        lda (PTR),y
        clc
        adc #GLYPHS             ; same glyph, next dither block
        sta (PTR),y
.skip
}

; --- second dim step, three quarters of the way down the trail -------------
!macro dimhalf {
        lda len,x
        lsr                     ; len/2
        sta TMP
        lsr                     ; len/4
        clc
        adc TMP                 ; 3*len/4
        sta TMP
        lda row,x
        sec
        sbc TMP
        cmp #ROWS
        bcs .skip
        tay
        +scrptr
        lda (PTR),y
        clc
        adc #GLYPHS
        sta (PTR),y
.skip
}

; --- the cell that has dropped off the end of the trail: colour it out -----
;     Writing black to colour RAM is one byte and leaves the glyph alone,
;     which is cheaper than blanking the screen code.
!macro erase {
        lda row,x
        sec
        sbc len,x
        cmp #ROWS
        bcs .skip
        tay
        +colptr
        lda #$00
        sta (PTR),y
.skip
}

; --- copy a whole block of glyphs through a per-pixel-row mask -------------
!macro mkblock .from, .to, .masks {
        lda #<(CHARSET + .from*GLYPHS*8)
        sta SRC
        lda #>(CHARSET + .from*GLYPHS*8)
        sta SRC+1
        lda #<(CHARSET + .to*GLYPHS*8)
        sta DST
        lda #>(CHARSET + .to*GLYPHS*8)
        sta DST+1
        ldx #GLYPHS
.glyph  ldy #$07
.brow   lda (SRC),y
        and .masks,y
        sta (DST),y
        dey
        bpl .brow
        lda SRC
        clc
        adc #$08
        sta SRC
        bcc .n1
        inc SRC+1
.n1     lda DST
        clc
        adc #$08
        sta DST
        bcc .n2
        inc DST+1
.n2     dex
        bne .glyph
}

; ===========================================================================
;  MAIN
; ===========================================================================
start:
        sei                     ; no KERNAL IRQ: rock steady raster timing,
                                ; and we can bank the character ROM in safely
        jsr buildchars          ; make the 255-character dithered font

        lda #$00
        sta $d020               ; black border
        sta $d021               ; black background
        sta $0286               ; clear the screen to black ink, so the
        jsr $e544               ; leftover screen codes stay invisible
        lda #D018VAL
        sta $d018               ; switch the VIC to our character set

        jsr mkrnd               ; fill the random table
!if MUSIC = 1 {
        jsr musinit             ; all three voices are free for music now
}

        jsr initcols

mainloop:
        lda #RASLINE            ; sync to the lower border
.wait   cmp $d012
        bne .wait

        jsr update
!if MUSIC = 1 {
        jsr mplay               ; one music tick per frame, same raster sync
}

        lda #$00                ; any key? (all keyboard rows selected)
        sta $dc00
        lda $dc01
        cmp #$ff
        beq mainloop

; --- put everything back the way BASIC likes it ----------------------------
exit:
!if MUSIC = 1 {
        jsr musoff              ; with MUSIC = 0 the SID is never touched
}
        lda #$ff
        sta $dc00
        lda #$15
        sta $d018               ; ROM character set again
        lda #$0e
        sta $d020
        lda #$06
        sta $d021
        lda #$0e
        sta $0286
        jsr $e544
        cli
        rts

; ===========================================================================
;  Fill rndtab with 256 glyph numbers, 0..GLYPHS-1
; ---------------------------------------------------------------------------
;  A 16 bit Galois LFSR, stepped eight times per byte so consecutive entries
;  are independent.  This used to be a read of $D41B, the SID voice 3
;  oscillator, which was free but pinned that voice to the noise waveform for
;  ever.  Doing it in software costs about 27000 cycles once, at boot, and
;  hands the third voice to the music.
; ===========================================================================
mkrnd:
        lda $d012               ; seed from the raster, never zero
        ora #$01
        sta seed
        lda #$c3
        sta seed+1
        ldx #$00
.byte   ldy #$08
.bit    lsr seed+1
        ror seed
        bcc .nofb
        lda seed+1
        eor #$b4                ; taps
        sta seed+1
.nofb   dey
        bne .bit
        lda seed
        and #$7f
        cmp #GLYPHS
        bcc .ok
        sbc #GLYPHS             ; fold 85..127 into range
.ok     sta rndtab,x
        inx
        bne .byte
        rts

; ===========================================================================
;  Give every column a random start row, speed and trail length
; ===========================================================================
initcols:
        ldx #COLS-1
.il     +rndglyph
        and #$1f
        sta row,x               ; stagger the columns
        +rndglyph
        and #$03
        tay
        lda spdtab,y            ; frames per row, from the speed table
        sta speed,x
        sta delay,x
        +rndglyph
        and #$0f
        clc
        adc #$06                ; trail 6..21 rows
        sta len,x
        dex
        bpl .il
        rts

; ===========================================================================
;  One frame
; ===========================================================================
update:
        ldx #COLS-1

ucol:
        dec delay,x
        beq uwork
        jmp unext               ; this column is not due yet: 8 cycles

uwork:
        lda speed,x
        sta delay,x
        inc row,x

        lda row,x               ; has the whole trail left the screen?
        sec
        sbc len,x
        bcc udraw
        cmp #ROWS
        bcc udraw

        lda #$00                ; respawn with new random parameters
        sta row,x
        +rndglyph
        and #$03
        tay
        lda spdtab,y
        sta speed,x
        sta delay,x
        +rndglyph
        and #$0f
        clc
        adc #$06
        sta len,x

udraw:
        +erase                  ; oldest cell   -> black
        +dimhalf                ; halfway down  -> 25% dither
        +dim 3                  ; 3 behind head -> 50% dither
        +shimmer 2, C_TR2       ; 2 behind head -> new glyph, body colour
        +fade 1, C_TR1          ; 1 behind head -> bright trail colour
        +head                   ; the head itself

unext:
        dex
        bmi udone
        jmp ucol                ; loop body is > 127 bytes, so JMP not BPL
udone:
        rts

; ===========================================================================
;  CHARACTER SET BUILDER  (runs once, at start-up)
; ---------------------------------------------------------------------------
;  Block 0  chars   0.. 84   full brightness   $3000
;  Block 1  chars  85..169   50% dither        $32A8
;  Block 2  chars 170..254   25% dither        $3550
; ===========================================================================
buildchars:
!if FONT = 1 {
        ; --- the built-in glyph set: 85 glyphs, 680 bytes, straight copy ---
        ldx #$00
.fcopy  lda fontdata,x          ; three overlapping 256-byte runs cover
        sta CHARSET,x           ; 0..679 exactly, with no 16-bit pointer
        lda fontdata+168,x
        sta CHARSET+168,x
        lda fontdata+424,x
        sta CHARSET+424,x
        inx
        bne .fcopy
} else {
        ; --- pull 85 glyphs out of the character ROM -----------------------
        lda $01
        and #$fb
        sta $01                 ; character ROM in at $D000 (I/O out!)

        lda #<CHARSET
        sta DST
        lda #>CHARSET
        sta DST+1
        ldx #$00
bcglyph:
        lda srctab,x            ; bit 7 = which ROM half, bits 0-6 = code
        and #$7f
        sta TMP
        lda #$00
        sta SRC+1
        lda TMP
        asl                     ; code * 8 into SRC (16 bit)
        rol SRC+1
        asl
        rol SRC+1
        asl
        rol SRC+1
        sta SRC
        lda SRC+1
        ora #$d0                ; upper case / graphics set at $D000
        ldy srctab,x
        bpl bcset1
        clc
        adc #$08                ; lower case set at $D800
bcset1:
        sta SRC+1
        ldy #$07
bccopy:
        lda (SRC),y
        sta (DST),y
        dey
        bpl bccopy
        lda DST
        clc
        adc #$08
        sta DST
        bcc bcnohi
        inc DST+1
bcnohi:
        inx
        cpx #GLYPHS
        bne bcglyph

        lda $01
        ora #$04
        sta $01                 ; I/O back in

  !if MIRROR = 1 {
        ; --- flip the 26 upper-case glyphs left-to-right -------------------
        lda #<(CHARSET+26*8)
        sta SRC
        lda #>(CHARSET+26*8)
        sta SRC+1
        ldx #26
mrglyph:
        ldy #$07
mrbyte:
        lda (SRC),y
        sty TMP2
        ldy #$08
mrbit:  asl                     ; bit 7 out of A ...
        ror TMP                 ; ... and into the top of TMP
        dey
        bne mrbit
        ldy TMP2
        lda TMP
        sta (SRC),y
        dey
        bpl mrbyte
        lda SRC
        clc
        adc #$08
        sta SRC
        bcc mrnohi
        inc SRC+1
mrnohi: dex
        bne mrglyph
  }
}

        +mkblock 0, 1, mask50   ; 50% dither copy
        +mkblock 0, 2, mask25   ; 25% dither copy
        rts

; ===========================================================================
;  DATA
; ===========================================================================

; --- THE SPEED KNOB -------------------------------------------------------
;     Frames per row, one of these four picked at random per column.  Bigger
;     numbers = slower rain.  Scale all four by the same factor to change the
;     overall speed without flattening the spread between columns.
spdtab: !byte 4,5,7,8

; --- dither masks, one per pixel row of the character ----------------------
mask50: !byte %10101010,%01010101,%10101010,%01010101
        !byte %10101010,%01010101,%10101010,%01010101
mask25: !byte %10001000,%01000100,%00100010,%00010001
        !byte %10001000,%01000100,%00100010,%00010001

!if FONT = 1 {
; --- the built-in rain glyphs ---------------------------------------------
;     An original 8x8 constructed script: angular marks, roughly half of them
;     mirror images of the other half, nothing readable as Latin.  Each glyph
;     is drawn above its eight bytes, one byte per pixel row, so it can be
;     edited straight in this listing.
fontdata:
!source "fontdata.inc"
} else {
; --- where each of the 85 ROM glyphs comes from ----------------------------
;     bit 7 set = lower-case ROM set ($D800), clear = graphics set ($D000)
srctab:
        ; 0-25   a-z
        !byte $81,$82,$83,$84,$85,$86,$87,$88,$89,$8a,$8b,$8c,$8d
        !byte $8e,$8f,$90,$91,$92,$93,$94,$95,$96,$97,$98,$99,$9a
        ; 26-51  A-Z   (mirrored afterwards if MIRROR = 1)
        !byte $01,$02,$03,$04,$05,$06,$07,$08,$09,$0a,$0b,$0c,$0d
        !byte $0e,$0f,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$1a
        ; 52-61  0-9
        !byte $30,$31,$32,$33,$34,$35,$36,$37,$38,$39
        ; 62-84  PETSCII graphics: lines, corners, pips and symbols
        !byte $41,$42,$43,$44,$45,$46,$47,$48,$49,$4a,$4b,$4d
        !byte $4e,$4f,$51,$53,$55,$56,$57,$58,$5a,$5b,$5e
}

; --- row -> screen address, so there is never a multiply -------------------
rowlo:
        !byte <(SCREEN+ 0*40),<(SCREEN+ 1*40),<(SCREEN+ 2*40),<(SCREEN+ 3*40)
        !byte <(SCREEN+ 4*40),<(SCREEN+ 5*40),<(SCREEN+ 6*40),<(SCREEN+ 7*40)
        !byte <(SCREEN+ 8*40),<(SCREEN+ 9*40),<(SCREEN+10*40),<(SCREEN+11*40)
        !byte <(SCREEN+12*40),<(SCREEN+13*40),<(SCREEN+14*40),<(SCREEN+15*40)
        !byte <(SCREEN+16*40),<(SCREEN+17*40),<(SCREEN+18*40),<(SCREEN+19*40)
        !byte <(SCREEN+20*40),<(SCREEN+21*40),<(SCREEN+22*40),<(SCREEN+23*40)
        !byte <(SCREEN+24*40)
colhi:
        !byte >($d800+ 0*40),>($d800+ 1*40),>($d800+ 2*40),>($d800+ 3*40)
        !byte >($d800+ 4*40),>($d800+ 5*40),>($d800+ 6*40),>($d800+ 7*40)
        !byte >($d800+ 8*40),>($d800+ 9*40),>($d800+10*40),>($d800+11*40)
        !byte >($d800+12*40),>($d800+13*40),>($d800+14*40),>($d800+15*40)
        !byte >($d800+16*40),>($d800+17*40),>($d800+18*40),>($d800+19*40)
        !byte >($d800+20*40),>($d800+21*40),>($d800+22*40),>($d800+23*40)
        !byte >($d800+24*40)
rowhi:
        !byte >(SCREEN+ 0*40),>(SCREEN+ 1*40),>(SCREEN+ 2*40),>(SCREEN+ 3*40)
        !byte >(SCREEN+ 4*40),>(SCREEN+ 5*40),>(SCREEN+ 6*40),>(SCREEN+ 7*40)
        !byte >(SCREEN+ 8*40),>(SCREEN+ 9*40),>(SCREEN+10*40),>(SCREEN+11*40)
        !byte >(SCREEN+12*40),>(SCREEN+13*40),>(SCREEN+14*40),>(SCREEN+15*40)
        !byte >(SCREEN+16*40),>(SCREEN+17*40),>(SCREEN+18*40),>(SCREEN+19*40)
        !byte >(SCREEN+20*40),>(SCREEN+21*40),>(SCREEN+22*40),>(SCREEN+23*40)
        !byte >(SCREEN+24*40)

; --- per-column state ------------------------------------------------------
seed:   !byte 0,0               ; LFSR state, used only at boot

        !align 255,0            ; rndtab must start on a page boundary
rndtab: !fill 256,0

row:    !fill COLS,0            ; head row, 0..24+len
delay:  !fill COLS,1            ; frames until the next step
speed:  !fill COLS,1            ; frames per row
len:    !fill COLS,8            ; trail length

!if MUSIC = 1 {
!source "music.inc"
}
