/**
 * Class tagging form: anyone scores a YouTube video on every trait in the Content Traits tab, and each
 * submission becomes a new column in the Manual Tagging tab (same layout the team has been filling by hand).
 *
 * Setup, once:
 *   1. Open the team spreadsheet → Extensions → Apps Script. Paste this file, save.
 *   2. Run buildTaggingForm and approve the permissions it asks for.
 *   3. The execution log prints two links: the form editor, and the link to share. Share the second one:
 *      it opens the form with every score already set to 0.
 *
 * Each submission lands in the form's own responses tab (created automatically, one row per submission) and
 * onTaggingSubmit adds a column to Manual Tagging: header = video title, a note with the URL and submit time,
 * one score per trait row. Two people tagging the same video make two columns.
 *
 * Rerunning buildTaggingForm builds a new form from the current trait list (e.g. after traits change). The
 * old form keeps accepting answers until you close or delete it in Google Drive.
 */

const TRAITS_TAB = 'Content Traits';
const MANUAL_TAB = 'Manual Tagging';
const URL_QUESTION = 'YouTube video URL';

// Same scale text the AI tagger is given (src/tag_videos.py), so people and the model score against one definition.
const LINEAR_SCALE = [
  'Score every 0-4 trait on this scale. Read "X" as the trait being scored.',
  '0 - Absent. Nothing in the video is X. A viewer would not associate the video with X.',
  '1 - Incidental. The creator did not intend X, but some part of the video has X value implicitly.',
  '2 - Explicit segment. The video as a whole is not X, but at least one part is deliberately X and signaled as such.',
  "3 - Featured. X is one of the video's stated purposes; a substantial dedicated portion is X, but the video also does other things.",
  '4 - Defining. The video is X and nothing else. Remove X and there is no video left.',
  'Tie-breakers: intent beats accident (explicit framing means at least 2); coverage moves you up (segment 2, major portion 3, whole 4); when torn between two levels, pick the lower.',
].join('\n');
const BINARY_SCALE = 'Yes/no traits: 1 if the trait is present anywhere in the video, even briefly; 0 if absent. When unsure, 0.';
const YOUTUBE_URL_PATTERN = '^(https?://)?(www\\.|m\\.)?(youtube\\.com/(watch\\?v=|shorts/|live/)|youtu\\.be/)[A-Za-z0-9_-]{11}.*$';


function buildTaggingForm() {
  const spreadsheet = SpreadsheetApp.getActiveSpreadsheet();
  const traits = readTraits(spreadsheet);

  const form = FormApp.create('YouTube video trait tagging');
  form.setDescription([
    'Help us measure what makes YouTube videos perform. Watch a video of your choice, paste its link, then score ' +
    'it on each trait below. Every score starts at 0: change only the traits that apply. About 15-25 minutes per video.',
    'No sign-in or email is collected.',
    '',
    LINEAR_SCALE,
    '',
    BINARY_SCALE,
  ].join('\n'))
    .setCollectEmail(false)
    .setProgressBar(true)
    .setConfirmationMessage('Thanks, your scores were recorded. Use the same link to tag another video.');

  form.addTextItem()
    .setTitle(URL_QUESTION)
    .setHelpText('The full link, e.g. https://www.youtube.com/watch?v=... or a Shorts link.')
    .setRequired(true)
    .setValidation(FormApp.createTextValidation()
      .requireTextMatchesPattern(YOUTUBE_URL_PATTERN)
      .setHelpText('Enter a YouTube video link.')
      .build());

  // Forms has no default answer for scale or choice questions, so defaults come from a pre-filled link.
  const defaults = [];
  let category = null;
  traits.forEach(function (trait) {
    if (trait.category !== category) {
      category = trait.category;
      form.addPageBreakItem()
        .setTitle(category)
        .setHelpText('0 Absent · 1 Incidental · 2 Explicit segment · 3 Featured · 4 Defining (full definitions on the first page).');
    }
    if (trait.scale === 'binary') {
      const item = form.addMultipleChoiceItem()
        .setTitle(trait.name)
        .setHelpText(trait.definition + ' (0 = absent, 1 = present)')
        .setChoiceValues(['0', '1'])
        .setRequired(true);
      defaults.push(item.createResponse('0'));
    } else {
      const item = form.addScaleItem()
        .setTitle(trait.name)
        .setHelpText(trait.definition)
        .setBounds(0, 4)
        .setLabels('Absent', 'Defining')
        .setRequired(true);
      defaults.push(item.createResponse(0));
    }
  });

  const prefilled = form.createResponse();
  defaults.forEach(function (itemResponse) { prefilled.withItemResponse(itemResponse); });

  form.setDestination(FormApp.DestinationType.SPREADSHEET, spreadsheet.getId());
  // One submit handler per spreadsheet; a rebuild replaces the old trigger instead of adding a second one.
  ScriptApp.getProjectTriggers()
    .filter(function (trigger) { return trigger.getHandlerFunction() === 'onTaggingSubmit'; })
    .forEach(function (trigger) { ScriptApp.deleteTrigger(trigger); });
  ScriptApp.newTrigger('onTaggingSubmit').forSpreadsheet(spreadsheet).onFormSubmit().create();

  Logger.log('Form editor: ' + form.getEditUrl());
  Logger.log('Share this link (every score starts at 0): ' + prefilled.toPrefilledUrl());
}


function onTaggingSubmit(e) {
  const answers = e.namedValues;
  const url = (answers[URL_QUESTION] || [''])[0].trim();
  if (!url) {
    return;  // a submission from some other form linked to this spreadsheet
  }
  const scores = {};
  Object.keys(answers).forEach(function (question) {
    scores[traitKey(question)] = answers[question][0];
  });
  const title = videoTitle(url);

  // Two submissions at the same moment would otherwise both pick the same empty column.
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(MANUAL_TAB);
    const data = sheet.getDataRange().getValues();
    const headerRow = data.findIndex(function (row) { return String(row[0]).trim() === 'Trait'; });
    if (headerRow < 0) {
      throw new Error('No "Trait" header cell in column A of ' + MANUAL_TAB);
    }
    let lastColumn = 0;
    data[headerRow].forEach(function (cell, index) { if (String(cell).trim()) { lastColumn = index; } });
    const newColumn = lastColumn + 2;  // 1-based column right after the last filled header

    const column = data.slice(headerRow + 1).map(function (row) {
      const score = scores[traitKey(String(row[0]))];
      return [score === undefined || score === '' ? '' : Number(score)];
    });
    const header = sheet.getRange(headerRow + 1, newColumn);
    header.setValue(title);
    header.setNote(url + '\nSubmitted ' + (answers['Timestamp'] || [''])[0]);
    sheet.getRange(headerRow + 2, newColumn, column.length, 1).setValues(column);
  } finally {
    lock.releaseLock();
  }
}


function readTraits(spreadsheet) {
  const rows = spreadsheet.getSheetByName(TRAITS_TAB).getDataRange().getValues();
  const header = rows[0].map(function (cell) { return String(cell).trim(); });
  const position = {};
  ['Category', 'Scale', 'Trait', 'Definition'].forEach(function (name) {
    position[name] = header.indexOf(name);
    if (position[name] < 0) {
      throw new Error(TRAITS_TAB + ' is missing the "' + name + '" column');
    }
  });
  return rows.slice(1)
    .filter(function (row) { return String(row[position.Trait]).trim(); })
    .map(function (row) {
      return {
        name: String(row[position.Trait]).trim(),
        category: String(row[position.Category]).trim(),
        scale: String(row[position.Scale]).trim().toLowerCase(),
        definition: String(row[position.Definition]).trim(),
      };
    });
}


// Same normalization as src/traits.py, so "Curiosity Gap Hook" in the form matches its Manual Tagging row.
function traitKey(name) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
}


function videoTitle(url) {
  try {
    const response = UrlFetchApp.fetch('https://www.youtube.com/oembed?format=json&url=' + encodeURIComponent(url),
                                       {muteHttpExceptions: true});
    if (response.getResponseCode() === 200) {
      return JSON.parse(response.getContentText()).title;
    }
  } catch (error) {
    Logger.log('Title lookup failed for ' + url + ': ' + error);
  }
  return url;
}
