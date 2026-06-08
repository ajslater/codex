<template>
  <div id="editPanel">
    <div id="editToolbar">
      <v-select
        v-model="selectedFormats"
        :items="formatChoices"
        label="Formats"
        density="compact"
        hide-details
        multiple
        chips
        class="formatSelect"
        @update:model-value="enforceMinFormat"
      />
      <v-spacer />
      <v-btn variant="text" @click="$emit('cancel')"> Cancel </v-btn>
      <v-btn
        :color="hasChanges ? 'primary' : 'grey-darken-1'"
        variant="flat"
        :loading="saving"
        :disabled="!hasChanges"
        @click="preSave"
      >
        Save Tags
      </v-btn>
    </div>
    <v-dialog v-model="confirmDialog" max-width="450">
      <v-card>
        <v-card-title>Confirm Tag Write</v-card-title>
        <v-card-text>
          <div>
            Writing tags to
            <strong>{{ confirmInfo.total }}</strong>
            comic{{ confirmInfo.total === 1 ? "" : "s" }}.
          </div>
          <div v-if="confirmInfo.needConversion > 0" class="conversionWarning">
            <div>
              {{ confirmInfo.needConversion }}
              comic{{ confirmInfo.needConversion === 1 ? "" : "s" }}
              will be converted to CBZ.
            </div>
            <div class="conversionHelpText">
              Writing tags to CBR, CB7, or CBT archives converts them to CBZ.
              Enable this to delete the original file after conversion.
            </div>
            <v-checkbox
              v-model="confirmDeleteOriginal"
              label="Delete original files after conversion"
              hide-details
              density="compact"
              class="mt-2"
            />
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirmDialog = false">Cancel</v-btn>
          <v-btn color="primary" variant="flat" @click="doSave">
            Write Tags
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <div class="sectionHeader">Publishing</div>
    <section class="mdSection">
      <div class="inlineRow">
        <div
          :title="isFieldDisabled('publisher') ? disabledTooltip : ''"
          class="flexItem"
        >
          <v-combobox
            v-model="patch.publisher"
            :items="collectionOptions('publisher')"
            :placeholder="collectionPlaceholder('publisher')"
            label="Publisher"
            hide-details
            density="compact"
            :disabled="isFieldDisabled('publisher')"
            :class="{
              fieldCleared: isCleared('publisher'),
              fieldChanged:
                isFieldChanged('publisher') && !isCleared('publisher'),
            }"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('publisher')"
                @toggle="toggleClear('publisher')"
              />
            </template>
          </v-combobox>
        </div>
        <div
          :title="isFieldDisabled('imprint') ? disabledTooltip : ''"
          class="flexItem"
        >
          <v-combobox
            v-model="patch.imprint"
            :items="collectionOptions('imprint')"
            :placeholder="collectionPlaceholder('imprint')"
            label="Imprint"
            hide-details
            density="compact"
            :disabled="isFieldDisabled('imprint')"
            :class="{
              fieldCleared: isCleared('imprint'),
              fieldChanged: isFieldChanged('imprint') && !isCleared('imprint'),
            }"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('imprint')"
                @toggle="toggleClear('imprint')"
              />
            </template>
          </v-combobox>
        </div>
      </div>
      <div class="inlineRow">
        <div
          :title="isFieldDisabled('series') ? disabledTooltip : ''"
          class="flexItem"
        >
          <v-combobox
            v-model="patch.series"
            :items="collectionOptions('series')"
            :placeholder="collectionPlaceholder('series')"
            label="Series"
            hide-details
            density="compact"
            :disabled="isFieldDisabled('series')"
            :class="{
              fieldCleared: isCleared('series'),
              fieldChanged: isFieldChanged('series') && !isCleared('series'),
            }"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('series')"
                @toggle="toggleClear('series')"
              />
            </template>
          </v-combobox>
        </div>
        <div
          :title="isFieldDisabled('volume') ? disabledTooltip : ''"
          class="flexItem"
        >
          <v-combobox
            v-model="patch.volume"
            :items="collectionOptions('volume')"
            :placeholder="collectionPlaceholder('volume')"
            label="Volume"
            hide-details
            density="compact"
            :disabled="isFieldDisabled('volume')"
            :class="{
              fieldCleared: isCleared('volume'),
              fieldChanged: isFieldChanged('volume') && !isCleared('volume'),
            }"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('volume')"
                @toggle="toggleClear('volume')"
              />
            </template>
          </v-combobox>
        </div>
        <div
          :title="isFieldDisabled('volume_count') ? disabledTooltip : ''"
          class="flexItem"
        >
          <v-text-field
            v-model="patch.volume_count"
            label="Volume Count"
            type="number"
            hide-details
            density="compact"
            :disabled="isFieldDisabled('volume_count')"
            :class="{
              fieldCleared: isCleared('volume_count'),
              fieldChanged:
                isFieldChanged('volume_count') && !isCleared('volume_count'),
            }"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('volume_count')"
                @toggle="toggleClear('volume_count')"
              />
            </template>
          </v-text-field>
        </div>
      </div>
      <div class="inlineRow">
        <div
          :title="isFieldDisabled('issue_number') ? disabledTooltip : ''"
          class="flexItem"
        >
          <v-text-field
            v-model="patch.issue_number"
            label="Issue Number"
            type="number"
            hide-details
            density="compact"
            :disabled="isFieldDisabled('issue_number')"
            :class="{
              fieldCleared: isCleared('issue_number'),
              fieldChanged:
                isFieldChanged('issue_number') && !isCleared('issue_number'),
            }"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('issue_number')"
                @toggle="toggleClear('issue_number')"
              />
            </template>
          </v-text-field>
        </div>
        <div
          :title="isFieldDisabled('issue_suffix') ? disabledTooltip : ''"
          class="flexItem"
        >
          <v-text-field
            v-model="patch.issue_suffix"
            label="Issue Suffix"
            hide-details
            density="compact"
            :disabled="isFieldDisabled('issue_suffix')"
            :class="{
              fieldCleared: isCleared('issue_suffix'),
              fieldChanged:
                isFieldChanged('issue_suffix') && !isCleared('issue_suffix'),
            }"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('issue_suffix')"
                @toggle="toggleClear('issue_suffix')"
              />
            </template>
          </v-text-field>
        </div>
        <div
          :title="isFieldDisabled('volume_issue_count') ? disabledTooltip : ''"
          class="flexItem"
        >
          <v-text-field
            v-model="patch.volume_issue_count"
            label="Issue Count"
            type="number"
            hide-details
            density="compact"
            :disabled="isFieldDisabled('volume_issue_count')"
            :class="{
              fieldCleared: isCleared('volume_issue_count'),
              fieldChanged:
                isFieldChanged('volume_issue_count') &&
                !isCleared('volume_issue_count'),
            }"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('volume_issue_count')"
                @toggle="toggleClear('volume_issue_count')"
              />
            </template>
          </v-text-field>
        </div>
      </div>
    </section>

    <div class="sectionHeader">Description</div>
    <section class="mdSection">
      <div :title="isFieldDisabled('summary') ? disabledTooltip : ''">
        <v-textarea
          v-model="patch.summary"
          label="Summary"
          rows="3"
          auto-grow
          hide-details
          density="compact"
          :disabled="isFieldDisabled('summary')"
          :class="{
            fieldCleared: isCleared('summary'),
            fieldChanged: isFieldChanged('summary') && !isCleared('summary'),
          }"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('summary')"
              @toggle="toggleClear('summary')"
            />
          </template>
        </v-textarea>
      </div>
      <div :title="isFieldDisabled('review') ? disabledTooltip : ''">
        <v-textarea
          v-model="patch.review"
          label="Review"
          rows="2"
          auto-grow
          hide-details
          density="compact"
          :disabled="isFieldDisabled('review')"
          :class="{
            fieldCleared: isCleared('review'),
            fieldChanged: isFieldChanged('review') && !isCleared('review'),
          }"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('review')"
              @toggle="toggleClear('review')"
            />
          </template>
        </v-textarea>
      </div>
    </section>

    <div class="sectionHeader">Credits</div>
    <v-table class="mdSection">
      <tbody>
        <tr v-for="role in creditRoles" :key="role">
          <td class="key" :class="{ labelChanged: isCreditRoleChanged(role) }">
            {{ role }}
          </td>
          <td :title="isFieldDisabled('credits') ? disabledTooltip : ''">
            <v-combobox
              v-model="creditsByRole[role]"
              multiple
              chips
              closable-chips
              hide-details
              density="compact"
              :disabled="isFieldDisabled('credits')"
              @update:model-value="creditsVersion++"
            />
          </td>
        </tr>
      </tbody>
    </v-table>
    <div class="tableFooter">
      <div
        v-if="availableRoles.length > 0"
        :title="isFieldDisabled('credits') ? disabledTooltip : ''"
      >
        <v-select
          v-model="selectedNewRole"
          :items="availableRoles"
          label="Add role..."
          density="compact"
          hide-details
          class="addRoleSelect"
          :disabled="isFieldDisabled('credits')"
          @update:model-value="addRole"
        />
      </div>
      <v-spacer />
      <v-btn
        v-if="creditRoles.length"
        variant="text"
        size="x-small"
        @click="clearField('credits')"
      >
        Clear All
      </v-btn>
    </div>

    <div class="sectionHeader">Details</div>
    <section class="mdSection detailsGrid">
      <div :title="isFieldDisabled('reading_direction') ? disabledTooltip : ''">
        <v-select
          v-model="patch.reading_direction"
          :items="readingDirectionItems"
          label="Reading Direction"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('reading_direction')"
          :class="{
            fieldCleared: isCleared('reading_direction'),
            fieldChanged:
              isFieldChanged('reading_direction') &&
              !isCleared('reading_direction'),
          }"
          @update:model-value="onFieldInput('reading_direction')"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('reading_direction')"
              @toggle="toggleClear('reading_direction')"
            />
          </template>
        </v-select>
      </div>
      <div :title="isFieldDisabled('original_format') ? disabledTooltip : ''">
        <v-select
          v-model="patch.original_format"
          :items="filteredOriginalFormats"
          label="Original Format"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('original_format')"
          :class="{
            fieldCleared: isCleared('original_format'),
            fieldChanged:
              isFieldChanged('original_format') &&
              !isCleared('original_format'),
          }"
          @update:model-value="onFieldInput('original_format')"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('original_format')"
              @toggle="toggleClear('original_format')"
            />
          </template>
        </v-select>
      </div>
      <div :title="isFieldDisabled('language') ? disabledTooltip : ''">
        <v-select
          v-model="patch.language"
          :items="languageChoices"
          label="Language"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('language')"
          :class="{
            fieldCleared: isCleared('language'),
            fieldChanged: isFieldChanged('language') && !isCleared('language'),
          }"
          @update:model-value="onFieldInput('language')"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('language')"
              @toggle="toggleClear('language')"
            />
          </template>
        </v-select>
      </div>
      <div :title="isFieldDisabled('age_rating') ? disabledTooltip : ''">
        <v-select
          v-model="patch.age_rating"
          :items="filteredAgeRatings"
          label="Age Rating"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('age_rating')"
          :class="{
            fieldCleared: isCleared('age_rating'),
            fieldChanged:
              isFieldChanged('age_rating') && !isCleared('age_rating'),
          }"
          @update:model-value="onFieldInput('age_rating')"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('age_rating')"
              @toggle="toggleClear('age_rating')"
            />
          </template>
        </v-select>
      </div>
      <div :title="isFieldDisabled('critical_rating') ? disabledTooltip : ''">
        <v-text-field
          v-model.number="patch.critical_rating"
          label="Critical Rating"
          type="number"
          min="0"
          max="5"
          step="0.1"
          :rules="criticalRatingRules"
          hide-details="auto"
          density="compact"
          :disabled="isFieldDisabled('critical_rating')"
          :class="{
            fieldCleared: isCleared('critical_rating'),
            fieldChanged:
              isFieldChanged('critical_rating') &&
              !isCleared('critical_rating'),
          }"
          @update:model-value="onFieldInput('critical_rating')"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('critical_rating')"
              @toggle="toggleClear('critical_rating')"
            />
          </template>
        </v-text-field>
      </div>
      <div
        class="monochromeRow"
        :class="{
          fieldCleared: isCleared('monochrome'),
          fieldChanged:
            isFieldChanged('monochrome') && !isCleared('monochrome'),
        }"
        :title="isFieldDisabled('monochrome') ? disabledTooltip : ''"
      >
        <v-checkbox
          v-model="patch.monochrome"
          label="Monochrome"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('monochrome')"
        />
        <ClearFieldIcon
          :cleared="isCleared('monochrome')"
          @toggle="toggleClear('monochrome')"
        />
      </div>
    </section>

    <v-expansion-panels variant="accordion" class="fileInfoPanel">
      <v-expansion-panel>
        <v-expansion-panel-title class="fileInfoTitle">
          File Info
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="fileInfoGrid">
            <span v-if="md?.createdAt" class="readOnlyField">
              <span class="readOnlyLabel">Created</span>
              {{ formatDateTime(md.createdAt) }}
            </span>
            <span v-if="md?.updatedAt" class="readOnlyField">
              <span class="readOnlyLabel">Updated</span>
              {{ formatDateTime(md.updatedAt) }}
            </span>
            <span v-if="totalSize" class="readOnlyField">
              <span class="readOnlyLabel">{{ sizeLabel }}</span>
              {{ totalSize }}
            </span>
            <span v-if="fileType" class="readOnlyField">
              <span class="readOnlyLabel">File Type</span>
              {{ fileType }}
            </span>
          </div>
          <div v-if="md?.path" class="readOnlyField pathField">
            <span class="readOnlyLabel">Path</span>
            {{ md.path }}
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>
    </v-expansion-panels>

    <div class="sectionHeader">Tags</div>
    <v-table class="mdSection">
      <tbody>
        <template v-for="tagKey in tagKeys" :key="tagKey">
          <tr
            :class="{
              fieldCleared: isCleared(tagKey),
              fieldChanged: isFieldChanged(tagKey) && !isCleared(tagKey),
            }"
          >
            <td class="key">
              {{ tagLabel(tagKey) }}
            </td>
            <td>
              <v-tooltip
                v-if="isFieldDisabled(tagKey)"
                :text="disabledTooltip"
                location="top"
              >
                <template #activator="{ props: tipProps }">
                  <div v-bind="tipProps">
                    <v-combobox
                      v-model="patch[tagKey]"
                      multiple
                      chips
                      closable-chips
                      hide-details
                      density="compact"
                      disabled
                      :class="{
                        fieldCleared: isCleared(tagKey),
                        fieldChanged:
                          isFieldChanged(tagKey) && !isCleared(tagKey),
                      }"
                    />
                  </div>
                </template>
              </v-tooltip>
              <v-combobox
                v-else
                v-model="patch[tagKey]"
                multiple
                chips
                closable-chips
                hide-details
                density="compact"
                :class="{
                  fieldCleared: isCleared(tagKey),
                  fieldChanged: isFieldChanged(tagKey) && !isCleared(tagKey),
                }"
              >
                <template #append-inner>
                  <ClearFieldIcon
                    :cleared="isCleared(tagKey)"
                    @toggle="toggleClear(tagKey)"
                  />
                </template>
              </v-combobox>
            </td>
          </tr>
          <tr v-if="tagKey === 'characters'" class="subSelectRow">
            <td class="key subSelectLabel">Main</td>
            <td>
              <v-tooltip
                v-if="!patch.characters.length"
                text="Add characters above first"
                location="top"
              >
                <template #activator="{ props: tipProps }">
                  <div v-bind="tipProps">
                    <v-select
                      v-model="patch.main_character"
                      :items="[]"
                      label="Main Character"
                      hide-details
                      density="compact"
                      disabled
                    />
                  </div>
                </template>
              </v-tooltip>
              <div
                v-else
                :title="isFieldDisabled('protagonist') ? disabledTooltip : ''"
              >
                <v-select
                  v-model="patch.main_character"
                  :items="patch.characters"
                  label="Main Character"
                  hide-details
                  density="compact"
                  :disabled="isFieldDisabled('protagonist')"
                  :class="{
                    fieldCleared: isCleared('main_character'),
                    fieldChanged:
                      isFieldChanged('main_character') &&
                      !isCleared('main_character'),
                  }"
                  @update:model-value="onFieldInput('main_character')"
                >
                  <template #append-inner>
                    <ClearFieldIcon
                      :cleared="isCleared('main_character')"
                      @toggle="toggleClear('main_character')"
                    />
                  </template>
                </v-select>
              </div>
            </td>
          </tr>
          <tr v-if="tagKey === 'teams'" class="subSelectRow">
            <td class="key subSelectLabel">Main</td>
            <td>
              <v-tooltip
                v-if="!patch.teams.length"
                text="Add teams above first"
                location="top"
              >
                <template #activator="{ props: tipProps }">
                  <div v-bind="tipProps">
                    <v-select
                      v-model="patch.main_team"
                      :items="[]"
                      label="Main Team"
                      hide-details
                      density="compact"
                      disabled
                    />
                  </div>
                </template>
              </v-tooltip>
              <div
                v-else
                :title="isFieldDisabled('protagonist') ? disabledTooltip : ''"
              >
                <v-select
                  v-model="patch.main_team"
                  :items="patch.teams"
                  label="Main Team"
                  hide-details
                  density="compact"
                  :disabled="isFieldDisabled('protagonist')"
                  :class="{
                    fieldCleared: isCleared('main_team'),
                    fieldChanged:
                      isFieldChanged('main_team') && !isCleared('main_team'),
                  }"
                  @update:model-value="onFieldInput('main_team')"
                >
                  <template #append-inner>
                    <ClearFieldIcon
                      :cleared="isCleared('main_team')"
                      @toggle="toggleClear('main_team')"
                    />
                  </template>
                </v-select>
              </div>
            </td>
          </tr>
        </template>
        <tr>
          <td class="key">Story Arcs</td>
          <td :title="isFieldDisabled('story_arcs') ? disabledTooltip : ''">
            <v-combobox
              v-model="storyArcNames"
              multiple
              chips
              closable-chips
              hide-details
              density="compact"
              :disabled="isFieldDisabled('story_arcs')"
              :class="{
                fieldCleared: isCleared('story_arcs'),
                fieldChanged:
                  isFieldChanged('story_arcs') && !isCleared('story_arcs'),
              }"
            >
              <template #append-inner>
                <ClearFieldIcon
                  :cleared="isCleared('story_arcs')"
                  @toggle="toggleClear('story_arcs')"
                />
              </template>
            </v-combobox>
          </td>
        </tr>
      </tbody>
    </v-table>

    <div class="sectionHeader">Universes</div>
    <v-table class="mdSection">
      <tbody>
        <tr v-for="(u, i) in universes" :key="i">
          <td :title="isFieldDisabled('universes') ? disabledTooltip : ''">
            <v-combobox
              v-model="universes[i].name"
              label="Universe"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('universes')"
            />
          </td>
          <td :title="isFieldDisabled('universes') ? disabledTooltip : ''">
            <v-text-field
              v-model="universes[i].designation"
              label="Designation"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('universes')"
            />
          </td>
          <td class="removeCol">
            <v-btn
              icon
              size="x-small"
              variant="text"
              @click="universes.splice(i, 1)"
            >
              &times;
            </v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>
    <div class="tableFooter">
      <div :title="isFieldDisabled('universes') ? disabledTooltip : ''">
        <v-btn
          variant="text"
          size="small"
          :disabled="isFieldDisabled('universes')"
          @click="universes.push({ name: '', designation: '' })"
        >
          + Add Universe
        </v-btn>
      </div>
      <v-spacer />
      <v-btn
        v-if="universes.length"
        variant="text"
        size="x-small"
        @click="clearField('universes')"
      >
        Clear All
      </v-btn>
    </div>

    <div class="sectionHeader">Identifiers</div>
    <v-table class="mdSection">
      <tbody>
        <tr v-for="(id, i) in identifiers" :key="i">
          <td :title="isFieldDisabled('identifiers') ? disabledTooltip : ''">
            <v-select
              v-model="identifiers[i].source"
              :items="identifierSourceChoices"
              label="Source"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('identifiers')"
            />
          </td>
          <td :title="isFieldDisabled('identifiers') ? disabledTooltip : ''">
            <v-select
              v-model="identifiers[i].id_type"
              :items="identifierTypeChoices"
              label="Type"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('identifiers')"
            />
          </td>
          <td :title="isFieldDisabled('identifiers') ? disabledTooltip : ''">
            <v-text-field
              v-model="identifiers[i].key"
              label="Key"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('identifiers')"
            />
          </td>
          <td class="removeCol">
            <v-btn
              icon
              size="x-small"
              variant="text"
              @click="identifiers.splice(i, 1)"
            >
              &times;
            </v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>
    <div class="tableFooter">
      <div :title="isFieldDisabled('identifiers') ? disabledTooltip : ''">
        <v-btn
          variant="text"
          size="small"
          :disabled="isFieldDisabled('identifiers')"
          @click="identifiers.push({ source: '', id_type: 'comic', key: '' })"
        >
          + Add Identifier
        </v-btn>
      </div>
      <div :title="isFieldDisabled('identifiers') ? disabledTooltip : ''">
        <v-btn
          variant="text"
          size="small"
          :disabled="isFieldDisabled('identifiers')"
          @click="addUrlDialog = true"
        >
          + Add URL
        </v-btn>
      </div>
      <v-spacer />
      <v-btn
        v-if="identifiers.length"
        variant="text"
        size="x-small"
        @click="clearField('identifiers')"
      >
        Clear All
      </v-btn>
    </div>

    <v-dialog v-model="addUrlDialog" max-width="500">
      <v-card>
        <v-card-title>Add Identifier from URL</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="identifierUrl"
            label="Paste URL"
            hide-details="auto"
            density="compact"
            autofocus
            :error-messages="urlError"
            @keyup.enter="parseIdentifierUrl"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="addUrlDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :loading="parsingUrl"
            :disabled="!identifierUrl"
            @click="parseIdentifierUrl"
          >
            Add
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <div class="sectionHeader">Notes</div>
    <section class="mdSection">
      <div :title="isFieldDisabled('notes') ? disabledTooltip : ''">
        <v-textarea
          v-model="patch.notes"
          label="Notes"
          rows="2"
          auto-grow
          hide-details
          density="compact"
          :disabled="isFieldDisabled('notes')"
          :class="{
            fieldCleared: isCleared('notes'),
            fieldChanged: isFieldChanged('notes') && !isCleared('notes'),
          }"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('notes')"
              @toggle="toggleClear('notes')"
            />
          </template>
        </v-textarea>
      </div>
      <div :title="isFieldDisabled('scan_info') ? disabledTooltip : ''">
        <v-text-field
          v-model="patch.scan_info"
          label="Scan Info"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('scan_info')"
          :class="{
            fieldCleared: isCleared('scan_info'),
            fieldChanged:
              isFieldChanged('scan_info') && !isCleared('scan_info'),
          }"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('scan_info')"
              @toggle="toggleClear('scan_info')"
            />
          </template>
        </v-text-field>
      </div>
    </section>
  </div>
</template>

<script>
import { mapActions, mapState } from "pinia";

import ClearFieldIcon from "@/components/metadata/edit-mode/clear-field-icon.vue";
import { capitalCase } from "text-case";
import prettyBytes from "pretty-bytes";

import { HTTP } from "@/api/v4/base";
import FORMAT_FIELD_SUPPORT from "@/choices/format-field-support.json";
import FORMAT_FIELD_VALUES from "@/choices/format-field-values.json";
import IDENTIFIER_SOURCES from "@/choices/identifier-sources.json";
import IDENTIFIER_TYPES from "@/choices/identifier-types.json";

const FORMAT_CHOICES = [
  { title: "MetronInfo", value: "METRON_INFO" },
  { title: "ComicInfo", value: "COMIC_INFO" },
];
import LANGUAGES from "@/choices/languages.json";
import { getDateTime } from "@/datetime";
import { useAdminStore } from "@/stores/admin";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";
import { useMetadataStore } from "@/stores/metadata";

const TAG_KEYS = [
  "genres",
  "characters",
  "teams",
  "locations",
  "series_groups",
  "stories",
  "tags",
];

// Single-value collection inputs whose dropdown is seeded from the opened
// group's own values. When a group spans more than one distinct value (e.g.
// case-variant publishers) the field starts blank so picking any option —
// including the first — registers as a change and enables Save.
const COLLECTION_FIELDS = Object.freeze([
  "publisher",
  "imprint",
  "series",
  "volume",
]);

const ALL_ROLES = Object.freeze([
  "Writer",
  "Author",
  "Plotter",
  "Plot",
  "Script",
  "Scripter",
  "Story",
  "Interviewer",
  "Translator",
  "Artist",
  "Penciller",
  "Breakdowns",
  "Pencils",
  "Illustrator",
  "Layouts",
  "Inker",
  "Finishes",
  "Inks",
  "Embellisher",
  "Ink Assists",
  "Colorist",
  "Colorer",
  "Colourer",
  "Colors",
  "Colours",
  "Color Designer",
  "Color Flats",
  "Color Separations",
  "Designer",
  "Digital Art Technician",
  "Gray Tone",
  "Letterer",
  "Cover",
  "Covers",
  "Cover Artist",
  "Editor",
  "Edits",
  "Editing",
]);

const CRITICAL_RATING_RULES = Object.freeze([
  (v) =>
    v === null ||
    v === "" ||
    v === undefined ||
    (Number.isFinite(Number(v)) && Number(v) >= 0 && Number(v) <= 5) ||
    "Must be 0.0–5.0",
]);

export default {
  name: "EditPanel",
  components: {
    ClearFieldIcon,
  },
  props: {
    book: {
      type: Object,
      required: true,
    },
  },
  emits: ["cancel", "saved"],
  data() {
    return {
      formatChoices: FORMAT_CHOICES,
      selectedFormats: ["COMIC_INFO"],
      languageChoices: LANGUAGES,
      identifierSourceChoices: IDENTIFIER_SOURCES,
      identifierTypeChoices: IDENTIFIER_TYPES,
      criticalRatingRules: CRITICAL_RATING_RULES,
      tagKeys: TAG_KEYS,
      saving: false,
      confirmDialog: false,
      confirmInfo: { total: 0, needConversion: 0 },
      confirmDeleteOriginal: false,
      addUrlDialog: false,
      identifierUrl: "",
      urlError: "",
      parsingUrl: false,
      clearedFields: new Set(),
      origSnapshot: null,
      creditsVersion: 0,
      selectedNewRole: null,
      creditsByRole: {},
      storyArcNames: [],
      universes: [],
      identifiers: [],
      patch: {
        publisher: "",
        imprint: "",
        series: "",
        volume: "",
        volume_issue_count: "",
        volume_count: "",
        issue_number: "",
        issue_suffix: "",
        summary: "",
        review: "",
        notes: "",
        scan_info: "",
        reading_direction: null,
        original_format: null,
        monochrome: false,
        language: null,
        age_rating: null,
        critical_rating: null,
        main_character: "",
        main_team: "",
        genres: [],
        characters: [],
        teams: [],
        locations: [],
        series_groups: [],
        stories: [],
        tags: [],
      },
    };
  },
  computed: {
    ...mapState(useMetadataStore, ["md"]),
    ...mapState(useAdminStore, ["taggingDefaults"]),
    ...mapState(useBrowserStore, {
      twentyFourHourTime: (state) => state.settings?.twentyFourHourTime,
    }),
    readingDirectionItems() {
      return this.unionFormatValues("reading_directions");
    },
    filteredOriginalFormats() {
      return this.unionFormatValues("original_formats");
    },
    filteredAgeRatings() {
      const items = this.unionFormatValues("age_ratings");
      const showCI = this.enabledFormats.includes("COMIC_INFO");
      if (!showCI) return items;
      return items.map((item) => {
        if (item.ci) {
          return { ...item, title: `${item.value} (${item.ci})` };
        }
        return item;
      });
    },
    enabledFormats() {
      return this.selectedFormats.length > 0
        ? this.selectedFormats
        : ["COMIC_INFO"];
    },
    supportedFields() {
      const supported = new Set();
      for (const fmt of this.enabledFormats) {
        const fields = FORMAT_FIELD_SUPPORT[fmt];
        if (fields) {
          for (const f of fields) supported.add(f);
        }
      }
      return supported;
    },
    disabledTooltip() {
      return "Not supported by selected metadata formats";
    },
    creditRoles() {
      return Object.keys(this.creditsByRole);
    },
    availableRoles() {
      const existing = new Set(this.creditRoles);
      return ALL_ROLES.filter((r) => !existing.has(r));
    },
    totalSize() {
      return this.md?.size > 0 ? prettyBytes(this.md.size) : "";
    },
    sizeLabel() {
      return this.md?.collection === "comics" ? "Size" : "Total Size";
    },
    fileType() {
      return this.md?.fileType || "";
    },
    creditsSerialized() {
      void this.creditsVersion;
      return JSON.stringify(this.creditsByRole);
    },
    currentSnapshot() {
      return {
        patch: JSON.stringify(this.patch),
        credits: this.creditsSerialized,
        storyArcs: JSON.stringify(this.storyArcNames),
        universes: JSON.stringify(this.universes),
        identifiers: JSON.stringify(this.identifiers),
      };
    },
    changedFields() {
      if (!this.origSnapshot) return new Set();
      const changed = new Set();
      const cur = this.currentSnapshot;
      const orig = this.origSnapshot;
      const curPatch = JSON.parse(cur.patch);
      const origPatch = JSON.parse(orig.patch);
      for (const k of Object.keys(curPatch)) {
        if (
          this.clearedFields.has(k) ||
          JSON.stringify(curPatch[k]) !== JSON.stringify(origPatch[k])
        ) {
          changed.add(k);
        }
      }
      if (this.clearedFields.has("credits") || cur.credits !== orig.credits) {
        changed.add("credits");
      }
      if (
        this.clearedFields.has("story_arcs") ||
        cur.storyArcs !== orig.storyArcs
      ) {
        changed.add("story_arcs");
      }
      if (
        this.clearedFields.has("universes") ||
        cur.universes !== orig.universes
      ) {
        changed.add("universes");
      }
      if (
        this.clearedFields.has("identifiers") ||
        cur.identifiers !== orig.identifiers
      ) {
        changed.add("identifiers");
      }
      return changed;
    },
    hasChanges() {
      return this.changedFields.size > 0;
    },
    changedCreditPersons() {
      void this.creditsVersion;
      if (!this.origSnapshot) return new Set();
      const orig = JSON.parse(this.origSnapshot.credits || "{}");
      const changed = new Set();
      const allRoles = new Set([
        ...Object.keys(this.creditsByRole),
        ...Object.keys(orig),
      ]);
      for (const role of allRoles) {
        const curArr = this.creditsByRole[role] || [];
        const origArr = orig[role] || [];
        if (JSON.stringify(curArr) !== JSON.stringify(origArr)) {
          for (const p of [...curArr, ...origArr]) changed.add(p);
        }
      }
      return changed;
    },
  },
  mounted() {
    this.loadTaggingDefaults();
    if (this.taggingDefaults?.defaultFormats?.length) {
      this.selectedFormats = [...this.taggingDefaults.defaultFormats];
    }
    this.initFromMetadata();
  },
  methods: {
    ...mapActions(useAdminStore, ["loadTaggingDefaults"]),
    isFieldDisabled(field) {
      return !this.supportedFields.has(field);
    },
    tagLabel(key) {
      if (key === "series_groups") return "Series Groups";
      if (key === "stories") {
        const hasMI = this.enabledFormats.includes("METRON_INFO");
        const hasCI = this.enabledFormats.includes("COMIC_INFO");
        if (hasMI && hasCI) return "Stories / Title";
        if (hasCI) return "Title";
        return "Stories";
      }
      return capitalCase(key);
    },
    enforceMinFormat(val) {
      if (!val || val.length === 0) {
        this.selectedFormats = this.lastFormats || ["COMIC_INFO"];
      } else {
        this.lastFormats = [...val];
      }
    },
    unionFormatValues(key) {
      const seen = new Set();
      const result = [];
      for (const fmt of this.enabledFormats) {
        const vals = FORMAT_FIELD_VALUES[fmt]?.[key];
        if (!vals) continue;
        for (const item of vals) {
          const v = typeof item === "string" ? item : item.value;
          if (!seen.has(v)) {
            seen.add(v);
            result.push(item);
          }
        }
      }
      return result;
    },
    isFieldChanged(field) {
      return this.changedFields.has(field);
    },
    isCreditRoleChanged(role) {
      if (!this.isFieldChanged("credits")) return false;
      void this.creditsVersion;
      const cur = this.creditsByRole[role] || [];
      const orig = JSON.parse(this.origSnapshot?.credits || "{}")[role] || [];
      if (JSON.stringify(cur) !== JSON.stringify(orig)) return true;
      if (!this.enabledFormats.includes("METRON_INFO")) return false;
      for (const person of cur) {
        if (this.changedCreditPersons.has(person)) return true;
      }
      return false;
    },
    isCleared(field) {
      return this.clearedFields.has(field);
    },
    toggleClear(field) {
      if (this.clearedFields.has(field)) {
        this.clearedFields.delete(field);
      } else {
        this.clearField(field);
      }
    },
    async parseIdentifierUrl() {
      this.urlError = "";
      this.parsingUrl = true;
      try {
        const response = await HTTP.post("/admin/parse-identifier-url", {
          url: this.identifierUrl,
        });
        this.identifiers.push({
          source: response.data.source,
          id_type: response.data.idType,
          key: response.data.key,
        });
        this.identifierUrl = "";
        this.addUrlDialog = false;
      } catch (error) {
        this.urlError = error.response?.data?.detail || "Could not parse URL";
      } finally {
        this.parsingUrl = false;
      }
    },
    onFieldInput(field) {
      if (this.patch[field]) {
        this.clearedFields.delete(field);
      }
    },
    clearField(field) {
      this.clearedFields.add(field);
      if (field in this.patch) {
        const val = this.patch[field];
        if (Array.isArray(val)) {
          this.patch[field] = [];
        } else if (typeof val === "boolean") {
          this.patch[field] = false;
        } else if (field === "critical_rating") {
          this.patch[field] = null;
        } else {
          this.patch[field] = "";
        }
      }
      if (field === "credits") {
        this.creditsByRole = {};
      } else if (field === "story_arcs") {
        this.storyArcNames = [];
      } else if (field === "universes") {
        this.universes = [];
      } else if (field === "identifiers") {
        this.identifiers = [];
      }
    },
    addRole(role) {
      if (role && !(role in this.creditsByRole)) {
        this.creditsByRole[role] = [];
      }
      this.selectedNewRole = null;
    },
    formatDateTime(ds) {
      return getDateTime(ds, this.twentyFourHourTime);
    },
    collectionOptions(field) {
      // Distinct, non-empty names from the opened group's list
      // (md.publisherList, md.imprintList, etc.) for the combobox dropdown.
      const list = this.md?.[`${field}List`] || [];
      const seen = new Set();
      const names = [];
      for (const o of list) {
        const n = o?.name;
        if (n === null || n === undefined || n === "") continue;
        const key = String(n);
        if (seen.has(key)) continue;
        seen.add(key);
        names.push(n);
      }
      return names;
    },
    collectionDistinctCount(field) {
      // Distinct values across the group's comics, counting a missing
      // collection (empty/null name — the default unnamed Publisher/Imprint/
      // …) as its own state. A group mixing an unnamed collection with a
      // named one (some comics have an imprint, some have none) has no common
      // value, so the field must blank — even though collectionOptions(),
      // which only feeds the dropdown, drops the empty entry.
      const list = this.md?.[`${field}List`] || [];
      const seen = new Set();
      for (const o of list) {
        const n = o?.name;
        seen.add(n === null || n === undefined ? "" : String(n));
      }
      return seen.size;
    },
    collectionPlaceholder(field) {
      return this.collectionDistinctCount(field) > 1
        ? "Multiple — select one to apply to all"
        : undefined;
    },
    initFromMetadata() {
      if (!this.md) return;

      // Text fields
      this.patch.summary = this.md.summary || "";
      this.patch.review = this.md.review || "";
      this.patch.notes = this.md.notes || "";
      this.patch.scan_info = this.md.scanInfo?.name || "";

      // Groups — seed from the group's own values. Blank when the group spans
      // more than one distinct value — including the "no collection" state — so
      // any pick registers as a change. collectionOptions drops empties for the
      // dropdown, so distinctness is counted separately.
      for (const field of COLLECTION_FIELDS) {
        const opts = this.collectionOptions(field);
        this.patch[field] =
          this.collectionDistinctCount(field) > 1 ? "" : (opts[0] ?? "");
      }
      this.patch.volume_issue_count = this.md.volumeIssueCount || "";
      this.patch.volume_count = this.md.seriesVolumeCount || "";
      this.patch.issue_number =
        this.md.issueNumber == null || this.md.issueNumber === ""
          ? ""
          : String(Number(this.md.issueNumber));
      this.patch.issue_suffix = this.md.issueSuffix || "";

      // Tags
      for (const key of TAG_KEYS) {
        const camelKey = key.replace(/_(\w)/g, (_, c) => c.toUpperCase());
        const tags = this.md[camelKey];
        if (tags?.length) {
          this.patch[key] = tags.map((t) => t.name);
        }
      }

      // Story arcs
      if (this.md.storyArcNumbers?.length) {
        this.storyArcNames = this.md.storyArcNumbers.map((a) => a.name);
      }

      // Credits — group by role
      if (this.md.credits?.length) {
        const grouped = {};
        for (const c of this.md.credits) {
          const role = c.role?.name || "Other";
          if (!(role in grouped)) {
            grouped[role] = [];
          }
          grouped[role].push(c.person?.name || "");
        }
        this.creditsByRole = grouped;
      }

      // Universes — name + optional designation
      if (this.md.universes?.length) {
        this.universes = this.md.universes.map((u) => ({
          name: u.name,
          designation: u.designation || "",
        }));
      }

      /* Identifiers — shaped as {pk, source, type, code, displayName, url} */
      if (this.md.identifiers?.length) {
        this.identifiers = this.md.identifiers.map((id) => ({
          source: id.source || "",
          id_type: id.type || "",
          key: id.code || "",
        }));
      }

      // Technical
      this.patch.reading_direction = this.md.readingDirection || null;
      this.patch.original_format = this.md.originalFormat?.name || null;
      this.patch.monochrome = Boolean(this.md.monochrome);
      this.patch.language = this.md.language?.name || null;
      this.patch.age_rating = this.md.ageRating?.name || null;
      this.patch.critical_rating =
        this.md.criticalRating == null ? null : Number(this.md.criticalRating);
      this.patch.main_character = this.md.mainCharacter?.name || "";
      this.patch.main_team = this.md.mainTeam?.name || "";

      this.origSnapshot = { ...this.currentSnapshot };
    },
    buildPatch() {
      const cbPatch = {};
      const cleared = this.clearedFields;
      const changed = this.changedFields;

      // Simple strings — only include if changed
      for (const key of ["summary", "review", "notes", "scan_info"]) {
        if (!changed.has(key)) continue;
        cbPatch[key] = cleared.has(key) ? "" : this.patch[key];
      }

      // Tag arrays — only include if changed
      for (const key of TAG_KEYS) {
        if (!changed.has(key)) continue;
        cbPatch[key] = cleared.has(key) ? {} : this.patch[key];
      }

      // Groups — only include if changed
      for (const key of ["publisher", "imprint"]) {
        if (!changed.has(key)) continue;
        cbPatch[key] = { name: cleared.has(key) ? "" : this.patch[key] };
      }
      if (changed.has("series") || changed.has("volume_count")) {
        const series = {};
        if (this.patch.series) series.name = this.patch.series;
        if (this.patch.volume_count) {
          const vc = parseInt(this.patch.volume_count, 10);
          if (!isNaN(vc)) series.volume_count = vc;
        }
        if (Object.keys(series).length) cbPatch.series = series;
      }
      if (changed.has("volume") || changed.has("volume_issue_count")) {
        if (this.patch.volume) {
          const num = parseInt(this.patch.volume, 10);
          if (!isNaN(num)) {
            const vol = { number: num };
            if (this.patch.volume_issue_count) {
              const ic = parseInt(this.patch.volume_issue_count, 10);
              if (!isNaN(ic)) vol.issue_count = ic;
            }
            cbPatch.volume = vol;
          }
        }
      }

      // Issue — number + suffix combine into the comicbox `issue` object;
      // comicbox computes `issue.name` from the parts. Update mode replaces
      // the key wholesale, so always send both current parts together.
      if (changed.has("issue_number") || changed.has("issue_suffix")) {
        const issue = {};
        if (!cleared.has("issue_number") && this.patch.issue_number !== "") {
          const num = Number(this.patch.issue_number);
          if (Number.isFinite(num)) issue.number = num;
        }
        if (!cleared.has("issue_suffix") && this.patch.issue_suffix) {
          issue.suffix = this.patch.issue_suffix;
        }
        cbPatch.issue = issue;
      }

      // Story arcs — only include if changed
      if (changed.has("story_arcs")) {
        if (cleared.has("story_arcs") || this.storyArcNames.length === 0) {
          cbPatch.arcs = {};
        } else {
          const arcs = {};
          for (const name of this.storyArcNames) arcs[name] = {};
          cbPatch.arcs = arcs;
        }
      }

      // Credits — only include if changed
      if (changed.has("credits")) {
        const credits = {};
        for (const [role, persons] of Object.entries(this.creditsByRole)) {
          for (const person of persons) {
            if (!person) continue;
            if (!(person in credits)) credits[person] = { roles: {} };
            if (role) credits[person].roles[role] = {};
          }
        }
        cbPatch.credits = Object.keys(credits).length > 0 ? credits : {};
      }

      // Universes — only include if changed
      if (changed.has("universes")) {
        if (cleared.has("universes") || this.universes.length === 0) {
          cbPatch.universes = {};
        } else {
          const univs = {};
          for (const u of this.universes) {
            if (u.name)
              univs[u.name] = u.designation
                ? { designation: u.designation }
                : {};
          }
          cbPatch.universes = univs;
        }
      }

      // Identifiers — only include if changed
      if (changed.has("identifiers")) {
        if (cleared.has("identifiers") || this.identifiers.length === 0) {
          cbPatch.identifiers = {};
        } else {
          const ids = {};
          for (const id of this.identifiers) {
            if (id.source && id.key) {
              const fullKey = id.id_type ? `${id.id_type}:${id.key}` : id.key;
              ids[id.source] = { key: fullKey, url: "" };
            }
          }
          cbPatch.identifiers = ids;
        }
      }

      // Technical select fields — only include if changed
      for (const key of [
        "reading_direction",
        "original_format",
        "language",
        "age_rating",
      ]) {
        if (!changed.has(key)) continue;
        cbPatch[key] = cleared.has(key) ? "" : this.patch[key];
      }
      if (changed.has("monochrome")) {
        cbPatch.monochrome = this.patch.monochrome;
      }

      // Critical Rating — clamp+round to canonical 0.0–5.0 (1 dp)
      if (changed.has("critical_rating")) {
        const raw = this.patch.critical_rating;
        if (cleared.has("critical_rating") || raw === null || raw === "") {
          cbPatch.critical_rating = null;
        } else {
          const n = Number(raw);
          if (Number.isFinite(n)) {
            cbPatch.critical_rating =
              Math.round(Math.max(0, Math.min(5, n)) * 10) / 10;
          }
        }
      }

      // Protagonist — only include if changed
      if (changed.has("main_character") || changed.has("main_team")) {
        const protagonist = this.patch.main_character || this.patch.main_team;
        cbPatch.protagonist = protagonist || "";
      }

      return cbPatch;
    },
    async preSave() {
      this.saving = true;
      const pks = this.book.ids || [this.book.pk];
      try {
        const response = await HTTP.post("/admin/tag-write/preflight", {
          collection: this.book.collection,
          pks: pks.map(String),
          formats: this.enabledFormats,
        });
        const data = response.data;
        this.confirmInfo = {
          total: data.total,
          needConversion: data.needConversion,
        };
        this.confirmDeleteOriginal = data.deleteOriginal || false;
        if (data.needConversion > 0 || data.total > 10) {
          this.confirmDialog = true;
          this.saving = false;
        } else {
          await this.doSave();
        }
      } catch (error) {
        useCommonStore().setErrors(error);
        this.saving = false;
      }
    },
    async doSave() {
      this.saving = true;
      this.confirmDialog = false;
      const pks = this.book.ids || [this.book.pk];
      const formats = this.enabledFormats;
      const cbPatch = this.buildPatch();

      try {
        const payload = {
          collection: this.book.collection,
          pks: pks.map(String),
          patch: JSON.stringify(cbPatch),
          mode: "update",
          formats,
        };
        if (this.confirmInfo.needConversion > 0) {
          payload.deleteOriginal = this.confirmDeleteOriginal;
        }
        await HTTP.post("/admin/tag-write", payload);
        useCommonStore().setSuccess("Tag write queued.");
        this.$emit("saved");
      } catch (error) {
        useCommonStore().setErrors(error);
      } finally {
        this.saving = false;
      }
    },
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";
@use "../table";

#editPanel {
  padding-bottom: 20px;
}

#editToolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 12px 0;
  position: sticky;
  top: 0;
  z-index: 1;
  background-color: rgb(var(--v-theme-surface));
}

.formatSelect {
  max-width: 280px;
}

.sectionHeader {
  margin-top: 20px;
  margin-bottom: 4px;
  font-size: 0.75em;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgb(var(--v-theme-textSecondary));
}

.mdSection {
  margin-top: 4px;
  background-color: rgb(var(--v-theme-surface));
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detailsGrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.inlineRow {
  display: flex;
  gap: 8px;
}

.inlineRow > * {
  flex: 1;
}

.fieldChanged :deep(.v-label) {
  color: rgb(var(--v-theme-primary));
}

td.labelChanged {
  color: rgb(var(--v-theme-primary));
}

.fieldCleared {
  opacity: 0.5;
}

.fieldCleared :deep(.v-label) {
  text-decoration: line-through;
}

.subSelectRow {
  opacity: 0.85;
}

.subSelectLabel {
  font-size: 0.85em;
  padding-left: 16px !important;
}

.monochromeRow {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tableFooter {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.addRoleSelect {
  max-width: 200px;
}

.fileInfoPanel {
  margin-top: 16px;
}

.fileInfoTitle {
  font-size: 0.85em;
  min-height: 36px !important;
  color: rgb(var(--v-theme-textSecondary));
}

.fileInfoGrid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px;
}

.pathField {
  margin-top: 8px;
  word-break: break-all;
}

.removeCol {
  width: 1%;
  white-space: nowrap;
}

.conversionWarning {
  margin-top: 12px;
  padding: 8px;
  border-radius: 4px;
  background-color: rgba(var(--v-theme-warning), 0.1);
}

.conversionHelpText {
  font-size: 0.85em;
  color: rgb(var(--v-theme-textSecondary));
  margin-top: 4px;
}

.readOnlyField {
  color: rgb(var(--v-theme-textSecondary));
  font-size: 0.85em;
}

.readOnlyLabel {
  font-size: 12px;
  display: block;
  color: rgb(var(--v-theme-textDisabled));
}

@media #{map.get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #editPanel {
    font-size: 12px;
  }

  .key {
    font-size: small;
  }
}
</style>
