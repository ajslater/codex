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
      <v-checkbox
        v-model="renameFile"
        :label="renameCheckboxLabel"
        :title="renameHint"
        hide-details
        density="compact"
        class="renameToggle"
      />
      <code
        v-if="!isMultipleComics && previewLabel"
        class="renamePreviewInline"
        :class="{ renamePreviewActive: renameFile && renameWillChange }"
        :title="renamePreviewTitle"
      >
        {{ previewLabel }}
      </code>
      <v-spacer />
      <v-btn variant="text" @click="$emit('cancel')"> Cancel </v-btn>
      <v-btn
        :color="canSave ? 'primary' : 'grey-darken-1'"
        variant="flat"
        :loading="saving"
        :disabled="!canSave"
        @click="preSave"
      >
        {{ saveButtonLabel }}
      </v-btn>
    </div>
    <v-dialog v-model="confirmDialog" max-width="450">
      <v-card>
        <v-card-title>{{ confirmTitle }}</v-card-title>
        <v-card-text>
          <div v-if="hasChanges">
            Writing tags to
            <strong>{{ confirmInfo.total }}</strong>
            comic{{ confirmInfo.total === 1 ? "" : "s" }}.
          </div>
          <div v-if="confirmInfo.skipped > 0" class="readOnlyWarning">
            {{ confirmInfo.skipped }}
            comic{{ confirmInfo.skipped === 1 ? "" : "s" }}
            in read-only libraries will be skipped.
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
          <div v-if="renameFile" class="renameInfo">
            <template v-if="renameChanges.length">
              <div class="renameWarning">
                Renaming rewrites files on disk and can't be undone
                automatically.
              </div>
              <div class="renameListLabel">
                Renaming
                <strong>{{ renameChanges.length }}</strong>
                file{{ renameChanges.length === 1 ? "" : "s" }} to the comicbox
                scheme:
              </div>
              <ul class="renamePreviewList">
                <li
                  v-for="(preview, index) in renameChanges"
                  :key="index"
                  class="renamePreviewItem"
                >
                  <span class="renameOld">{{ preview.old }}</span>
                  <span class="renameArrow">→</span>
                  <code class="renamePreview">{{ preview.new }}</code>
                </li>
              </ul>
              <div v-if="renameUnchangedCount" class="renameHelpText">
                {{ renameUnchangedCount }}
                file{{ renameUnchangedCount === 1 ? "" : "s" }} already match
                the comicbox scheme and won't change.
              </div>
              <div v-if="renamePreviewsTruncated" class="renameHelpText">
                …and {{ confirmInfo.total - renamePreviews.length }} more.
              </div>
            </template>
            <div v-else-if="renamePreviews.length" class="renameHelpText">
              All selected files already match the comicbox scheme — nothing to
              rename.
            </div>
            <div v-else class="renameHelpText">
              Files will be renamed to the comicbox scheme.
            </div>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" @click="confirmDialog = false">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="flat"
            :disabled="renameNoop"
            @click="doSave"
          >
            {{ confirmButtonLabel }}
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
      <div class="inlineRow">
        <div
          :title="
            isFieldDisabled('alternative_issue_number') ? disabledTooltip : ''
          "
          class="flexItem"
        >
          <v-text-field
            v-model="patch.alternative_issue_number"
            label="Alternative Issue Number"
            type="number"
            hide-details
            density="compact"
            :disabled="isFieldDisabled('alternative_issue_number')"
            :class="{
              fieldCleared: isCleared('alternative_issue_number'),
              fieldChanged:
                isFieldChanged('alternative_issue_number') &&
                !isCleared('alternative_issue_number'),
            }"
            @update:model-value="onFieldInput('alternative_issue_number')"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('alternative_issue_number')"
                @toggle="toggleClear('alternative_issue_number')"
              />
            </template>
          </v-text-field>
        </div>
        <div
          :title="
            isFieldDisabled('alternative_issue_suffix') ? disabledTooltip : ''
          "
          class="flexItem"
        >
          <v-text-field
            v-model="patch.alternative_issue_suffix"
            label="Alternative Issue Suffix"
            hide-details
            density="compact"
            :disabled="isFieldDisabled('alternative_issue_suffix')"
            :class="{
              fieldCleared: isCleared('alternative_issue_suffix'),
              fieldChanged:
                isFieldChanged('alternative_issue_suffix') &&
                !isCleared('alternative_issue_suffix'),
            }"
            @update:model-value="onFieldInput('alternative_issue_suffix')"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('alternative_issue_suffix')"
                @toggle="toggleClear('alternative_issue_suffix')"
              />
            </template>
          </v-text-field>
        </div>
      </div>
      <div class="inlineRow">
        <div
          :title="isFieldDisabled('year') ? disabledTooltip : ''"
          class="flexItem"
        >
          <v-text-field
            v-model.number="patch.year"
            label="Year"
            type="number"
            min="0"
            max="9999"
            :rules="yearRules"
            hide-details="auto"
            density="compact"
            :disabled="isFieldDisabled('year')"
            :class="{
              fieldCleared: isCleared('year'),
              fieldChanged: isFieldChanged('year') && !isCleared('year'),
            }"
            @update:model-value="onFieldInput('year')"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('year')"
                @toggle="toggleClear('year')"
              />
            </template>
          </v-text-field>
        </div>
        <div
          :title="isFieldDisabled('month') ? disabledTooltip : ''"
          class="flexItem"
        >
          <v-text-field
            v-model.number="patch.month"
            label="Month"
            type="number"
            min="1"
            max="12"
            :rules="monthRules"
            hide-details="auto"
            density="compact"
            :disabled="isFieldDisabled('month')"
            :class="{
              fieldCleared: isCleared('month'),
              fieldChanged: isFieldChanged('month') && !isCleared('month'),
            }"
            @update:model-value="onFieldInput('month')"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('month')"
                @toggle="toggleClear('month')"
              />
            </template>
          </v-text-field>
        </div>
        <div
          :title="isFieldDisabled('day') ? disabledTooltip : ''"
          class="flexItem"
        >
          <v-text-field
            v-model.number="patch.day"
            label="Day"
            type="number"
            min="1"
            max="31"
            :rules="dayRules"
            hide-details="auto"
            density="compact"
            :disabled="isFieldDisabled('day')"
            :class="{
              fieldCleared: isCleared('day'),
              fieldChanged: isFieldChanged('day') && !isCleared('day'),
            }"
            @update:model-value="onFieldInput('day')"
          >
            <template #append-inner>
              <ClearFieldIcon
                :cleared="isCleared('day')"
                @toggle="toggleClear('day')"
              />
            </template>
          </v-text-field>
        </div>
      </div>
      <div :title="isFieldDisabled('collection_title') ? disabledTooltip : ''">
        <v-text-field
          v-model="patch.collection_title"
          label="Collection Title"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('collection_title')"
          :class="{
            fieldCleared: isCleared('collection_title'),
            fieldChanged:
              isFieldChanged('collection_title') &&
              !isCleared('collection_title'),
          }"
          @update:model-value="onFieldInput('collection_title')"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('collection_title')"
              @toggle="toggleClear('collection_title')"
            />
          </template>
        </v-text-field>
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
      <div :title="isFieldDisabled('country') ? disabledTooltip : ''">
        <v-select
          v-model="patch.country"
          :items="countryChoices"
          label="Country"
          hide-details
          density="compact"
          :disabled="isFieldDisabled('country')"
          :class="{
            fieldCleared: isCleared('country'),
            fieldChanged: isFieldChanged('country') && !isCleared('country'),
          }"
          @update:model-value="onFieldInput('country')"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('country')"
              @toggle="toggleClear('country')"
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
      <div :title="isFieldDisabled('community_rating') ? disabledTooltip : ''">
        <v-text-field
          v-model.number="patch.community_rating"
          label="Community Rating"
          type="number"
          min="0"
          max="5"
          step="0.1"
          :rules="communityRatingRules"
          hide-details="auto"
          density="compact"
          :disabled="isFieldDisabled('community_rating')"
          :class="{
            fieldCleared: isCleared('community_rating'),
            fieldChanged:
              isFieldChanged('community_rating') &&
              !isCleared('community_rating'),
          }"
          @update:model-value="onFieldInput('community_rating')"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('community_rating')"
              @toggle="toggleClear('community_rating')"
            />
          </template>
        </v-text-field>
      </div>
      <div
        :title="
          isFieldDisabled('community_rating_count') ? disabledTooltip : ''
        "
      >
        <v-text-field
          v-model.number="patch.community_rating_count"
          label="Rating Count"
          type="number"
          min="1"
          step="1"
          :rules="communityRatingCountRules"
          hide-details="auto"
          density="compact"
          :disabled="isFieldDisabled('community_rating_count')"
          :class="{
            fieldCleared: isCleared('community_rating_count'),
            fieldChanged:
              isFieldChanged('community_rating_count') &&
              !isCleared('community_rating_count'),
          }"
          @update:model-value="onFieldInput('community_rating_count')"
        >
          <template #append-inner>
            <ClearFieldIcon
              :cleared="isCleared('community_rating_count')"
              @toggle="toggleClear('community_rating_count')"
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
          <tr
            v-if="tagKey === 'teams'"
            :class="{
              fieldCleared: isCleared('protagonist'),
              fieldChanged:
                isFieldChanged('protagonist') && !isCleared('protagonist'),
            }"
          >
            <td class="key">Protagonist</td>
            <td>
              <v-tooltip
                v-if="!protagonistItems.length"
                text="Add characters or teams above first"
                location="top"
              >
                <template #activator="{ props: tipProps }">
                  <div v-bind="tipProps">
                    <v-select
                      v-model="patch.protagonist"
                      :items="[]"
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
                  v-model="patch.protagonist"
                  :items="protagonistItems"
                  hide-details
                  density="compact"
                  :disabled="isFieldDisabled('protagonist')"
                  :class="{
                    fieldCleared: isCleared('protagonist'),
                    fieldChanged:
                      isFieldChanged('protagonist') &&
                      !isCleared('protagonist'),
                  }"
                  @update:model-value="onFieldInput('protagonist')"
                >
                  <template #append-inner>
                    <ClearFieldIcon
                      :cleared="isCleared('protagonist')"
                      @toggle="toggleClear('protagonist')"
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

    <div class="sectionHeader">Alternate Series</div>
    <v-table class="mdSection">
      <tbody>
        <tr v-for="(reprint, i) in reprints" :key="i">
          <td :title="isFieldDisabled('reprints') ? disabledTooltip : ''">
            <v-text-field
              v-model="reprints[i].series_name"
              label="Series"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('reprints')"
            />
          </td>
          <td :title="isFieldDisabled('reprint_volume') ? disabledTooltip : ''">
            <v-text-field
              v-model="reprints[i].volume"
              label="Volume"
              type="number"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('reprint_volume')"
            />
          </td>
          <td :title="isFieldDisabled('reprints') ? disabledTooltip : ''">
            <v-text-field
              v-model="reprints[i].issue"
              label="Issue"
              hide-details
              density="compact"
              :disabled="isFieldDisabled('reprints')"
            />
          </td>
          <td
            :title="isFieldDisabled('reprint_language') ? disabledTooltip : ''"
          >
            <v-select
              v-model="reprints[i].language"
              :items="languageChoices"
              label="Language"
              clearable
              hide-details
              density="compact"
              :disabled="isFieldDisabled('reprint_language')"
            />
          </td>
          <td class="removeCol">
            <v-btn
              icon
              size="x-small"
              variant="text"
              @click="reprints.splice(i, 1)"
            >
              &times;
            </v-btn>
          </td>
        </tr>
      </tbody>
    </v-table>
    <div class="tableFooter">
      <div :title="isFieldDisabled('reprints') ? disabledTooltip : ''">
        <v-btn
          variant="text"
          size="small"
          :disabled="isFieldDisabled('reprints')"
          @click="
            reprints.push({
              series_name: '',
              volume: '',
              issue: '',
              language: null,
            })
          "
        >
          + Add Alternate Series
        </v-btn>
      </div>
      <v-spacer />
      <v-btn
        v-if="reprints.length"
        variant="text"
        size="x-small"
        @click="clearField('reprints')"
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
import COUNTRIES from "@/choices/countries.json";
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

// Numeric fields that clear to null rather than "" (a cleared number is
// absent, not an empty string).
const NULL_CLEARED_FIELDS = Object.freeze(
  new Set([
    "community_rating",
    "community_rating_count",
    "year",
    "month",
    "day",
  ]),
);

const COMMUNITY_RATING_RULES = Object.freeze([
  (v) =>
    v === null ||
    v === "" ||
    v === undefined ||
    (Number.isFinite(Number(v)) && Number(v) >= 0 && Number(v) <= 5) ||
    "Must be 0.0–5.0",
]);

// The publish date parts and their bounds. comicbox bounds month and day and
// silently clamps them on write; year it leaves unbounded, but Comic.year is a
// positive small int whose date derivation clamps to python's MINYEAR/MAXYEAR.
// Bounding here keeps what the archive gets to what the field validated.
const DATE_PART_BOUNDS = Object.freeze({
  year: Object.freeze([1, 9999]),
  month: Object.freeze([1, 12]),
  day: Object.freeze([1, 31]),
});
const DATE_PARTS = Object.freeze(Object.keys(DATE_PART_BOUNDS));

const intRangeRules = ([min, max]) =>
  Object.freeze([
    (v) =>
      v === null ||
      v === "" ||
      v === undefined ||
      (Number.isInteger(Number(v)) && Number(v) >= min && Number(v) <= max) ||
      `Must be ${min}–${max}`,
  ]);
const YEAR_RULES = intRangeRules(DATE_PART_BOUNDS.year);
const MONTH_RULES = intRangeRules(DATE_PART_BOUNDS.month);
const DAY_RULES = intRangeRules(DATE_PART_BOUNDS.day);

const choiceValueForTitle = (choices, named) => {
  // pycountry-backed fields arrive as their long name; fall back to the raw
  // value for a code the serializer could not expand.
  const title = named?.name;
  if (!title) return null;
  return choices.find((choice) => choice.title === title)?.value ?? title;
};

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
      countryChoices: COUNTRIES,
      identifierSourceChoices: IDENTIFIER_SOURCES,
      identifierTypeChoices: IDENTIFIER_TYPES,
      communityRatingRules: COMMUNITY_RATING_RULES,
      yearRules: YEAR_RULES,
      monthRules: MONTH_RULES,
      dayRules: DAY_RULES,
      tagKeys: TAG_KEYS,
      saving: false,
      confirmDialog: false,
      confirmInfo: {
        total: 0,
        needConversion: 0,
        skipped: 0,
      },
      confirmDeleteOriginal: false,
      renameFile: false,
      renameHint:
        "Rename the comic file to the comicbox scheme derived from its tags.",
      renamePreviews: [],
      renamePreviewTimer: null,
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
      reprints: [],
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
        alternative_issue_number: "",
        alternative_issue_suffix: "",
        collection_title: "",
        year: null,
        month: null,
        day: null,
        summary: "",
        review: "",
        notes: "",
        scan_info: "",
        reading_direction: null,
        original_format: null,
        monochrome: false,
        language: null,
        country: null,
        age_rating: null,
        community_rating: null,
        community_rating_count: null,
        protagonist: "",
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
    communityRatingCountRules() {
      // A count without an average can't persist anywhere (MetronInfo's
      // CommunityRating requires AverageRating), so block count-only edits.
      return [
        (v) => {
          if (v === null || v === "" || v === undefined) return true;
          const n = Number(v);
          if (!Number.isInteger(n) || n < 1)
            return "Must be a whole number ≥ 1";
          const average = this.patch.community_rating;
          if (average === null || average === "") {
            return "Requires a community rating";
          }
          return true;
        },
      ];
    },
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
    protagonistItems() {
      // One protagonist, picked from the entered characters and teams.
      return [...new Set([...this.patch.characters, ...this.patch.teams])];
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
        reprints: JSON.stringify(this.reprints),
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
        this.clearedFields.has("reprints") ||
        cur.reprints !== orig.reprints
      ) {
        changed.add("reprints");
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
    canSave() {
      // Tag edits are always saveable. Otherwise the rename toggle enables
      // Save on its own (a pure "fix my filename" action) — except when we
      // already know that single-comic rename is a no-op.
      if (this.hasChanges) {
        return true;
      }
      return this.renameFile && !this.renameSingleNoop;
    },
    comicCount() {
      // A tag edit spans either an explicit multi-selection (book.ids) or a
      // container's children (book.childCount, e.g. a whole series/folder).
      return Math.max(
        this.book?.ids?.length || 0,
        this.book?.childCount || 0,
        1,
      );
    },
    isMultipleComics() {
      return this.comicCount > 1;
    },
    isRenameOnly() {
      // Rename with no tag edits: the operation is purely a rename.
      return !this.hasChanges && this.renameFile;
    },
    renameActionLabel() {
      return this.isMultipleComics ? "Rename Files" : "Rename File";
    },
    renameCheckboxLabel() {
      return this.isMultipleComics ? "Rename files" : "Rename file";
    },
    saveButtonLabel() {
      // Label the button for its actual effect: a pure rename until a tag is
      // altered, pluralized by how many comics are selected.
      return this.isRenameOnly ? this.renameActionLabel : "Save Tags";
    },
    confirmButtonLabel() {
      return this.isRenameOnly ? this.renameActionLabel : "Write Tags";
    },
    confirmTitle() {
      return this.isRenameOnly ? "Confirm Rename" : "Confirm Tag Write";
    },
    renamePreviewsTruncated() {
      return (
        this.renamePreviews.length > 0 &&
        this.confirmInfo.total > this.renamePreviews.length
      );
    },
    renameChanges() {
      // Previews whose new name actually differs from the current one — the
      // files a rename would really touch. A name equal to the current one is
      // a no-op, not a rename.
      return this.renamePreviews.filter((p) => p.new && p.new !== p.old);
    },
    renameUnchangedCount() {
      return this.renamePreviews.filter((p) => p.new && p.new === p.old).length;
    },
    renameWillChange() {
      // Single-comic inline: does the one previewed file actually get renamed?
      const preview = this.renamePreviews[0];
      return Boolean(preview && preview.new && preview.new !== preview.old);
    },
    renameSingleNoop() {
      // A single comic whose loaded preview shows the rename wouldn't change
      // anything (same name, or no name could be built). Only asserted once
      // the preview has loaded so the button isn't disabled while it fetches.
      return (
        !this.isMultipleComics &&
        this.renamePreviews.length > 0 &&
        !this.renameWillChange
      );
    },
    renamePreviewTitle() {
      if (this.renameFile && this.previewLabel && !this.renameWillChange) {
        return "Already matches the comicbox scheme";
      }
      return this.previewLabel;
    },
    renameNoop() {
      // Rename-only where every previewed file already matches: confirming
      // would do nothing. (Not claimed when the preview list was capped, since
      // files beyond the cap might still change.)
      return (
        this.isRenameOnly &&
        this.renamePreviews.length > 0 &&
        this.renameChanges.length === 0 &&
        !this.renamePreviewsTruncated
      );
    },
    renameSignature() {
      // The inputs the comicbox filename preview depends on. Empty when the
      // toggle is off so the (moderately heavy) patch build is skipped and the
      // preview watcher clears. The pending patch and delete keys are both
      // included so the preview tracks unsaved edits and clears alike.
      if (!this.renameFile) {
        return "";
      }
      return `${this.enabledFormats.join(",")}|${JSON.stringify(this.buildPatch())}`;
    },
    currentFileName() {
      // Basename of the opened comic's path (empty for multi-comic groups
      // that carry no single path).
      const path = this.md?.path || "";
      return path ? path.split(/[/\\]/).pop() : "";
    },
    previewLabel() {
      // The single-comic inline pill: the comicbox-scheme name the tags would
      // produce (rename on) or the file's current name (rename off), reading
      // as a before → after. Multi-comic previews live in the confirm dialog.
      return this.renameFile
        ? this.renamePreviews[0]?.new || ""
        : this.currentFileName;
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
  watch: {
    renameSignature() {
      // Refresh the inline single-comic preview when the toggle flips on or
      // the pending tags change. Debounced so keystrokes don't spam the
      // archive. Multi-comic selections skip the live fetch (it would open
      // every archive on each edit) and are previewed in the confirm dialog.
      if (!this.renameFile) {
        this.renamePreviews = [];
        return;
      }
      if (this.isMultipleComics) {
        return;
      }
      this.scheduleRenamePreview();
    },
    protagonistItems(newItems, oldItems) {
      // Removing the picked character/team clears the pick. A protagonist
      // seeded from the DB but absent from the entered lists survives
      // load: oldItems is the pre-init empty list on the first fire.
      const name = this.patch.protagonist;
      if (name && oldItems.includes(name) && !newItems.includes(name)) {
        this.patch.protagonist = "";
      }
    },
  },
  mounted() {
    this.loadTaggingDefaults();
    if (this.taggingDefaults?.defaultFormats?.length) {
      this.selectedFormats = [...this.taggingDefaults.defaultFormats];
    }
    this.renameFile = Boolean(this.taggingDefaults?.renameFiles);
    this.initFromMetadata();
  },
  beforeUnmount() {
    if (this.renamePreviewTimer) {
      clearTimeout(this.renamePreviewTimer);
    }
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
        } else if (NULL_CLEARED_FIELDS.has(field)) {
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
      } else if (field === "reprints") {
        this.reprints = [];
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
      this.patch.alternative_issue_number =
        this.md.alternativeIssueNumber == null ||
        this.md.alternativeIssueNumber === ""
          ? ""
          : String(Number(this.md.alternativeIssueNumber));
      this.patch.alternative_issue_suffix =
        this.md.alternativeIssueSuffix || "";
      this.patch.collection_title = this.md.collectionTitle || "";

      // Publish date — three independent parts; a comic may have only a year.
      for (const part of DATE_PARTS) {
        const value = this.md[part];
        this.patch[part] = value == null ? null : Number(value);
      }

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

      // Alternate series — the panel renders the composed `name`, but the
      // editor rebuilds comicbox's nested reprint from the flat columns.
      if (this.md.reprints?.length) {
        this.reprints = this.md.reprints.map((reprint) => ({
          series_name: reprint.seriesName || "",
          volume:
            reprint.volumeNumber == null ? "" : String(reprint.volumeNumber),
          issue: reprint.issue || "",
          language: reprint.language || null,
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
      // The API serializes these to their long English names; the choices are
      // keyed by the two-letter code comicbox writes, so map back or the
      // current value matches no item and re-picking it looks like an edit.
      this.patch.language = choiceValueForTitle(LANGUAGES, this.md.language);
      this.patch.country = choiceValueForTitle(COUNTRIES, this.md.country);
      this.patch.age_rating = this.md.ageRating?.name || null;
      this.patch.community_rating =
        this.md.communityRating == null
          ? null
          : Number(this.md.communityRating);
      this.patch.community_rating_count =
        this.md.communityRatingCount == null
          ? null
          : Number(this.md.communityRatingCount);
      // Protagonist is stored as mainCharacter XOR mainTeam.
      this.patch.protagonist =
        this.md.mainCharacter?.name || this.md.mainTeam?.name || "";

      this.origSnapshot = { ...this.currentSnapshot };
    },
    buildReprints() {
      // comicbox nests a reprint's parts under series/volume; codex stores
      // them flat. A row without a series name names nothing, so it's
      // dropped rather than written as an empty alternate.
      const reprints = [];
      for (const row of this.reprints) {
        if (!row.series_name) continue;
        const reprint = { series: { name: row.series_name } };
        const number = parseInt(row.volume, 10);
        if (!isNaN(number)) reprint.volume = { number };
        if (row.issue) reprint.issue = row.issue;
        if (row.language) reprint.language = row.language;
        reprints.push(reprint);
      }
      return reprints;
    },
    buildPatch() {
      // Returns { patch, deleteKeys }. A merge write can only add or replace
      // values — comicbox prunes empty patch values on schema load — so
      // cleared or emptied fields travel as comicbox delete_keys paths, the
      // write API's explicit clear mechanism.
      const cbPatch = {};
      const deleteKeys = [];
      const cleared = this.clearedFields;
      const changed = this.changedFields;

      // Simple strings — only include if changed
      for (const key of [
        "summary",
        "review",
        "notes",
        "scan_info",
        "collection_title",
      ]) {
        if (!changed.has(key)) continue;
        if (cleared.has(key) || !this.patch[key]) deleteKeys.push(key);
        else cbPatch[key] = this.patch[key];
      }

      // Tag arrays — only include if changed
      for (const key of TAG_KEYS) {
        if (!changed.has(key)) continue;
        if (cleared.has(key) || this.patch[key].length === 0)
          deleteKeys.push(key);
        else cbPatch[key] = this.patch[key];
      }

      // Groups — only include if changed
      for (const key of ["publisher", "imprint"]) {
        if (!changed.has(key)) continue;
        if (cleared.has(key) || !this.patch[key]) deleteKeys.push(key);
        else cbPatch[key] = { name: this.patch[key] };
      }
      if (changed.has("series") || changed.has("volume_count")) {
        const series = {};
        if (this.patch.series) series.name = this.patch.series;
        if (this.patch.volume_count) {
          const vc = parseInt(this.patch.volume_count, 10);
          if (!isNaN(vc)) series.volume_count = vc;
        }
        if (Object.keys(series).length) cbPatch.series = series;
        else deleteKeys.push("series");
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
        } else {
          deleteKeys.push("volume");
        }
      }

      // Issue and its alternate — number + suffix combine into a comicbox
      // issue object; comicbox computes the object's `name` from the parts.
      // Update mode replaces the key wholesale, so always send both current
      // parts together.
      for (const key of ["issue", "alternative_issue"]) {
        const numberField = `${key}_number`;
        const suffixField = `${key}_suffix`;
        if (!changed.has(numberField) && !changed.has(suffixField)) continue;
        const issue = {};
        if (!cleared.has(numberField) && this.patch[numberField] !== "") {
          const num = Number(this.patch[numberField]);
          if (Number.isFinite(num)) issue.number = num;
        }
        if (!cleared.has(suffixField) && this.patch[suffixField]) {
          issue.suffix = this.patch[suffixField];
        }
        if (Object.keys(issue).length) cbPatch[key] = issue;
        else deleteKeys.push(key);
      }

      // Publish date — the parts combine into the comicbox `date` object.
      // Update mode replaces the key wholesale, so send every surviving part
      // whenever any one changed; a cleared part just drops out of the
      // replacement and only a fully empty date needs the delete key.
      //
      // That replacement also drops any cover_date/store_date the archive
      // carried, and codex keeps no columns to resend them. comicbox
      // rederives cover_date (MetronInfo's CoverDate) from a full trio, so
      // only a partial date loses it — but store_date is never rederived and
      // a MetronInfo StoreDate does not survive a date edit.
      if (DATE_PARTS.some((part) => changed.has(part))) {
        const date = {};
        for (const part of DATE_PARTS) {
          if (cleared.has(part)) continue;
          const raw = this.patch[part];
          if (raw === null || raw === "") continue;
          const num = Math.round(Number(raw));
          if (!Number.isFinite(num)) continue;
          // Nothing gates Save on the field rules, so bound the value here
          // too: comicbox silently clamps month and day but writes any year
          // it is handed, and Comic.year is a positive small int.
          const [min, max] = DATE_PART_BOUNDS[part];
          date[part] = Math.min(max, Math.max(min, num));
        }
        if (Object.keys(date).length) cbPatch.date = date;
        else deleteKeys.push("date");
      }

      // Story arcs — only include if changed
      if (changed.has("story_arcs")) {
        if (cleared.has("story_arcs") || this.storyArcNames.length === 0) {
          deleteKeys.push("arcs");
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
        if (Object.keys(credits).length > 0) cbPatch.credits = credits;
        else deleteKeys.push("credits");
      }

      // Universes — only include if changed
      if (changed.has("universes")) {
        if (cleared.has("universes") || this.universes.length === 0) {
          deleteKeys.push("universes");
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

      // Alternate series — only include if changed
      if (changed.has("reprints")) {
        const reprints = this.buildReprints();
        if (reprints.length) cbPatch.reprints = reprints;
        else deleteKeys.push("reprints");
      }

      // Identifiers — only include if changed
      if (changed.has("identifiers")) {
        if (cleared.has("identifiers") || this.identifiers.length === 0) {
          deleteKeys.push("identifiers");
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
        "country",
        "age_rating",
      ]) {
        if (!changed.has(key)) continue;
        if (cleared.has(key) || !this.patch[key]) deleteKeys.push(key);
        else cbPatch[key] = this.patch[key];
      }
      // Monochrome is a tri-state tag: yes, no, or absent. Clearing must
      // remove it rather than write a false, which would assert the comic
      // is known to be color (comicbox 4.5.1 writes both booleans).
      if (changed.has("monochrome")) {
        if (cleared.has("monochrome")) deleteKeys.push("monochrome");
        else cbPatch.monochrome = this.patch.monochrome;
      }

      // Community Rating — average clamped+rounded to canonical 0.0–5.0
      // (1 dp) plus an optional integer vote count. Like `issue`, update
      // mode replaces the key wholesale, so send both current parts
      // whenever either changed. An empty average clears the whole key —
      // a count alone can't persist (MetronInfo requires AverageRating).
      if (
        changed.has("community_rating") ||
        changed.has("community_rating_count")
      ) {
        const raw = cleared.has("community_rating")
          ? null
          : this.patch.community_rating;
        const n = Number(raw);
        if (raw === null || raw === "" || !Number.isFinite(n)) {
          deleteKeys.push("community_rating");
        } else {
          const community = {
            average_rating: Math.round(Math.max(0, Math.min(5, n)) * 10) / 10,
          };
          const count = cleared.has("community_rating_count")
            ? null
            : Number(this.patch.community_rating_count);
          if (Number.isInteger(count) && count >= 1) {
            community.rating_count = count;
          }
          cbPatch.community_rating = community;
        }
      }

      // Protagonist — only include if changed. The importer resolves the
      // name to main_character or main_team and nulls the other on
      // re-import.
      if (changed.has("protagonist")) {
        if (cleared.has("protagonist") || !this.patch.protagonist)
          deleteKeys.push("protagonist");
        else cbPatch.protagonist = this.patch.protagonist;
      }

      return { patch: cbPatch, deleteKeys };
    },
    scheduleRenamePreview() {
      if (this.renamePreviewTimer) {
        clearTimeout(this.renamePreviewTimer);
      }
      this.renamePreviewTimer = setTimeout(this.fetchRenamePreview, 400);
    },
    async fetchRenamePreview() {
      // Ask the backend for the comicbox-scheme name the current tags would
      // produce (the scheme lives in comicbox, so it can't be built here).
      if (!this.renameFile) {
        this.renamePreviews = [];
        return;
      }
      const pks = this.book.ids || [this.book.pk];
      const { patch, deleteKeys } = this.hasChanges
        ? this.buildPatch()
        : { patch: {}, deleteKeys: [] };
      try {
        const response = await HTTP.post("/admin/tag-write/preflight", {
          collection: this.book.collection,
          pks: pks.map(String),
          formats: this.enabledFormats,
          patch: JSON.stringify(patch),
          deleteKeys,
        });
        this.renamePreviews = response.data.filenamePreviews || [];
      } catch {
        this.renamePreviews = [];
      }
    },
    async preSave() {
      this.saving = true;
      const pks = this.book.ids || [this.book.pk];
      // Rename-only (no tag edits) sends an empty patch so no tags are
      // written; the preview then reflects the archive's current metadata.
      const { patch, deleteKeys } = this.hasChanges
        ? this.buildPatch()
        : { patch: {}, deleteKeys: [] };
      try {
        const response = await HTTP.post("/admin/tag-write/preflight", {
          collection: this.book.collection,
          pks: pks.map(String),
          formats: this.enabledFormats,
          patch: JSON.stringify(patch),
          deleteKeys,
        });
        const data = response.data;
        this.confirmInfo = {
          total: data.total,
          needConversion: data.needConversion,
          skipped: data.skipped || 0,
        };
        this.renamePreviews = data.filenamePreviews || [];
        this.confirmDeleteOriginal = data.deleteOriginal || false;
        // Renaming rewrites files on disk — higher risk than a tag write — so
        // always confirm when it's enabled. Otherwise only prompt for archive
        // conversions or large batches.
        const needsConfirm =
          this.renameFile || data.needConversion > 0 || data.total > 10;
        if (needsConfirm) {
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
      const { patch, deleteKeys } = this.hasChanges
        ? this.buildPatch()
        : { patch: {}, deleteKeys: [] };

      try {
        const payload = {
          collection: this.book.collection,
          pks: pks.map(String),
          patch: JSON.stringify(patch),
          deleteKeys,
          mode: "update",
          formats,
          rename: this.renameFile,
        };
        if (this.confirmInfo.needConversion > 0) {
          payload.deleteOriginal = this.confirmDeleteOriginal;
        }
        const response = await HTTP.post("/admin/tag-write", payload);
        const skipped = response.data?.skipped || 0;
        let message = "Tag write queued.";
        if (skipped > 0) {
          message += ` ${skipped} comic${skipped === 1 ? "" : "s"} in read-only libraries skipped.`;
        }
        useCommonStore().setSuccess(message);
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

.conversionWarning,
.readOnlyWarning {
  margin-top: 12px;
  padding: 8px;
  border-radius: 4px;
  background-color: rgba(var(--v-theme-warning), 0.1);
}

.conversionHelpText,
.renameHelpText {
  font-size: 0.85em;
  color: rgb(var(--v-theme-textSecondary));
  margin-top: 4px;
}

.renameToggle {
  flex: 0 0 auto;
}

.renamePreviewInline {
  /* Size to the filename when it fits the free toolbar space; when it
     doesn't, shrink to that space and scroll horizontally rather than
     truncating. The v-spacer keeps the buttons right-aligned. */
  flex: 0 1 auto;
  min-width: 0;
  overflow-x: auto;
  white-space: nowrap;
  font-size: 0.85em;
  padding: 1px 6px;
  border-radius: 3px;
  background-color: rgba(var(--v-theme-on-surface), 0.08);
  color: rgb(var(--v-theme-textSecondary));
  scrollbar-width: thin;
}

.renamePreviewActive {
  /* The new name (rename on) reads as the primary action; the current name
     (rename off) stays muted. */
  color: rgb(var(--v-theme-primary));
  background-color: rgba(var(--v-theme-primary), 0.1);
}

.renameInfo {
  margin-top: 12px;
}

.renameWarning {
  margin-bottom: 8px;
  padding: 8px;
  border-radius: 4px;
  background-color: rgba(var(--v-theme-warning), 0.1);
  color: rgb(var(--v-theme-warning));
}

.renameListLabel {
  margin-bottom: 6px;
}

.renamePreviewList {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 220px;
  overflow-y: auto;
}

.renamePreviewItem {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px;
  padding: 2px 0;
  font-size: 0.85em;
}

.renamePreviewItem + .renamePreviewItem {
  border-top: 1px solid rgba(var(--v-theme-on-surface), 0.06);
}

.renameOld {
  color: rgb(var(--v-theme-textSecondary));
  word-break: break-all;
}

.renameArrow {
  color: rgb(var(--v-theme-textDisabled));
}

.renamePreview {
  padding: 1px 4px;
  border-radius: 3px;
  background-color: rgba(var(--v-theme-on-surface), 0.08);
  word-break: break-all;
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
